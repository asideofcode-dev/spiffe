/*
 * mini_backend.c — teaching sketch of a postmaster-started backend.
 *
 * Real Postgres passes -P<fd>; the child inherits that TCP connection and
 * talks the FE/BE protocol on it. Here we just read a line and reply.
 */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int
parse_port_fd(int argc, char **argv)
{
    for (int i = 1; i < argc; i++) {
        if (argv[i][0] == '-' && argv[i][1] == 'P')
            return atoi(argv[i] + 2);
    }
    return -1;
}

int
main(int argc, char **argv)
{
    int sock;
    char buf[512];
    ssize_t n;
    char reply[640];

    sock = parse_port_fd(argc, argv);
    if (sock < 0) {
        fprintf(stderr, "mini_backend: need -P<fd> (started by mini_postmaster)\n");
        return 1;
    }

    dprintf(sock, "mini_backend[%d]: hello, you are connected on fd %d\n",
            (int)getpid(), sock);

    n = read(sock, buf, sizeof(buf) - 1);
    if (n < 0) {
        perror("read");
        close(sock);
        return 1;
    }
    buf[n] = '\0';

    /* strip trailing newline for the log line */
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r'))
        buf[--n] = '\0';

    fprintf(stderr, "mini_backend[%d]: got %zd bytes: \"%s\"\n",
            (int)getpid(), n, buf);

    snprintf(reply, sizeof(reply),
             "mini_backend[%d]: echo: %s\n", (int)getpid(), buf);
    if (write(sock, reply, strlen(reply)) < 0)
        perror("write");

    close(sock);
    return 0;
}
