/*
 * mini_postmaster.c — teaching sketch of Postgres95's listen→accept→fork→exec flow.
 *
 * Mirrors (simplified):
 *   StreamServerPort  → socket/bind/listen
 *   ServerLoop        → select
 *   StreamConnection  → accept
 *   BackendStartup    → fork + execv with -P<fd>
 *
 * Not a database. Just enough networking/process plumbing to poke with nc/telnet.
 */
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

static void
reaper(int sig)
{
    (void)sig;
    while (waitpid(-1, NULL, WNOHANG) > 0)
        ;
}

static int
stream_server_port(short port_name)
{
    int fd;
    struct sockaddr_in sin;
    int on = 1;

    fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        perror("socket");
        return -1;
    }

    /* modern convenience; original Postgres95 did not set this */
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));

    memset(&sin, 0, sizeof(sin));
    sin.sin_family = AF_INET;
    sin.sin_port = htons(port_name);
    /* sin_addr left zero → INADDR_ANY */

    if (bind(fd, (struct sockaddr *)&sin, sizeof(sin)) < 0) {
        perror("bind");
        close(fd);
        return -1;
    }

    if (listen(fd, SOMAXCONN) < 0) {
        perror("listen");
        close(fd);
        return -1;
    }

    return fd;
}

static int
do_exec_backend(const char *backend_path, int client_fd)
{
    char *av[8];
    char portbuf[32];
    int ac = 0;

    snprintf(portbuf, sizeof(portbuf), "-P%d", client_fd);

    av[ac++] = (char *)backend_path;
    av[ac++] = "-p";          /* "started by postmaster" (like real Postgres) */
    av[ac++] = portbuf;       /* hand the accepted TCP fd to the child */
    av[ac] = NULL;

    return execv(av[0], av);
}

int
main(int argc, char **argv)
{
    short port = 15432;
    const char *backend_path;
    int listen_fd;
    char self_dir[4096];
    char backend_buf[4096];

    if (argc >= 2)
        port = (short)atoi(argv[1]);

    /* default: sibling binary next to this one */
    if (argc >= 3) {
        backend_path = argv[2];
    } else {
        ssize_t n = readlink("/proc/self/exe", self_dir, sizeof(self_dir) - 1);
        if (n < 0) {
            perror("readlink");
            return 1;
        }
        self_dir[n] = '\0';
        char *slash = strrchr(self_dir, '/');
        if (slash)
            *slash = '\0';
        snprintf(backend_buf, sizeof(backend_buf), "%s/mini_backend", self_dir);
        backend_path = backend_buf;
    }

    signal(SIGCHLD, reaper);

    listen_fd = stream_server_port(port);
    if (listen_fd < 0)
        return 1;

    printf("mini_postmaster: listening on 0.0.0.0:%d\n", port);
    printf("mini_postmaster: will exec backend: %s\n", backend_path);
    printf("mini_postmaster: try:  echo hello | nc 127.0.0.1 %d\n", port);
    fflush(stdout);

    for (;;) {
        fd_set rmask;
        struct sockaddr_in raddr;
        socklen_t addrlen = sizeof(raddr);
        int client_fd;
        pid_t pid;

        FD_ZERO(&rmask);
        FD_SET(listen_fd, &rmask);

        if (select(listen_fd + 1, &rmask, NULL, NULL, NULL) < 0) {
            if (errno == EINTR)
                continue;
            perror("select");
            return 1;
        }

        if (!FD_ISSET(listen_fd, &rmask))
            continue;

        client_fd = accept(listen_fd, (struct sockaddr *)&raddr, &addrlen);
        if (client_fd < 0) {
            if (errno == EINTR)
                continue;
            perror("accept");
            continue;
        }

        printf("mini_postmaster: accepted fd=%d from %s:%d\n",
               client_fd, inet_ntoa(raddr.sin_addr), ntohs(raddr.sin_port));
        fflush(stdout);

        pid = fork();
        if (pid < 0) {
            perror("fork");
            close(client_fd);
            continue;
        }

        if (pid == 0) {
            /* child: close listen socket, exec backend with -P<client_fd> */
            close(listen_fd);
            if (do_exec_backend(backend_path, client_fd) < 0) {
                perror("execv");
                _exit(1);
            }
        }

        /* parent: close its copy; child owns the connection now */
        close(client_fd);
        printf("mini_postmaster: spawned backend pid=%d\n", (int)pid);
        fflush(stdout);
    }
}
