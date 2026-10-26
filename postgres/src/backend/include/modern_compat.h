/* Compatibility shims so Postgres95 1.01 can compile on modern Linux/glibc. */
#ifndef PG95_MODERN_COMPAT_H
#define PG95_MODERN_COMPAT_H

#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdio.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <signal.h>
#include <ctype.h>
#include <time.h>
#include <limits.h>
#include <sys/ipc.h>
#include <sys/sem.h>
#include <sys/shm.h>

/* Older code often used these without prototypes. */
#ifndef MAXPATHLEN
#define MAXPATHLEN PATH_MAX
#endif

/*
 * Linux/glibc: X/Open says the application must define union semun.
 * Postgres95 assumes the OS header provides it.
 */
#if defined(__linux__)
# ifndef HAVE_UNION_SEMUN
#  define HAVE_UNION_SEMUN 1
union semun {
	int val;
	struct semid_ds *buf;
	unsigned short *array;
	struct seminfo *__buf;
};
# endif
#endif

#endif /* PG95_MODERN_COMPAT_H */
