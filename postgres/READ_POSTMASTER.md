# Annotated reading helper — `postmaster.c`

Source (tap to open on phone):
[`src/backend/postmaster/postmaster.c` @ `d31084e`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c)

This file is the **listener process**: accept TCP clients, authenticate, `fork` a child, `execv` the same binary as a backend with `-P<socket-fd>`. You do **not** need to know SQL to read it.

Use this page beside the GitHub file viewer: each section below is a **slice** of the C with syntax notes and “where does that name come from?” links.

---

## 1. C crib sheet (only what this file uses)

### Preprocessor (`#…`)

| You see | Meaning |
|---------|---------|
| `#include "foo.h"` | Paste that header’s declarations into this file (project header). |
| `#include <stdio.h>` | Same, but from the system C library. |
| `#ifndef WIN32` … `#endif` | “If `WIN32` is **not** defined, include this block.” Compile-time if/else. |
| `#ifdef HBA` … `#else` … `#endif` | “If `HBA` **is** defined, use this; else use that.” |
| `#if defined(PORTNAME_linux)` | Same idea: test a `#define` set by the build (here: Linux). |
| `#define FORK() fork()` | Text substitution: later `FORK()` becomes `fork()`. |
| `/* … */` | Comment (ignored by the compiler). |

`#ifdef` is **not** a runtime `if`. The unused branch is deleted before the code is compiled. That is why you see Windows and Unix variants of the same function in one file.

### Storage / linkage keywords

| You see | Meaning |
|---------|---------|
| `static int ServerSock` | File-private variable: other `.c` files cannot see it. |
| `static void pmdie(…)` | File-private function: only callable from this `.c`. |
| `extern char *DataDir` | “Defined in another `.c`; I only declare it here.” Linker finds the real one. |
| `int PostmasterMain(…)` | **Not** `static` → exported; `main.c` can call it. |
| `typedef struct bkend { … } Backend` | Create a type name `Backend` for that struct shape. |

### Types & pointers (very short)

| You see | Meaning |
|---------|---------|
| `int pid` | Integer (process id here). |
| `char *progname` | Pointer to characters = C string (or NULL). |
| `Port *port` | Pointer to a `Port` struct (defined in [`pqcomm.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.h)). |
| `port->sock` | Field `sock` inside the struct `port` points at. |
| `&ServerSock` | Address of variable `ServerSock` (pass “out” parameters). |
| `(Port *) calloc(…)` | Allocate memory; cast the `void*` result to `Port*`. |
| `(void) umask(…)` | Call for side effect; cast return value away (ignore it). |
| `NULL` | Null pointer (points at nothing). |

### Control flow you’ll meet

| You see | Meaning |
|---------|---------|
| `for (;;)` | Infinite loop (the listen loop). |
| `while ((opt = getopt(…)) != EOF)` | Classic argv parsing loop. |
| `switch (opt) { case 'p': … }` | Branch on one character / enum value. |
| `/*FALLTHROUGH*/` | Intentionally no `break` — next `case` also runs. |
| `return(STATUS_OK)` | Leave function; `STATUS_OK` is `0` ([`postgres.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/include/postgres.h)). |

### Signals & process words (Unix)

| Word | Meaning in this file |
|------|----------------------|
| `fork` / `vfork` | Duplicate process; child gets `0`, parent gets child’s pid. |
| `execv` | Replace current process image with another program (same binary path here). |
| `signal(SIGINT, pmdie)` | When Ctrl-C arrives, call `pmdie`. |
| `waitpid` | Reap a dead child; get its exit status. |
| `select` | Sleep until one of several sockets is readable. |

---

## 2. Story of the file (one screen)

```
PostmasterMain
  ├─ parse argv (-p port, -D data dir, -B buffers, …)
  ├─ checkDataDir()
  ├─ StreamServerPort()          → listen socket
  ├─ reset_shared()              → shm + semaphores
  ├─ signal handlers (pmdie, reaper, …)
  └─ ServerLoop()                → forever
        ├─ select()
        ├─ ConnCreate()          → accept() new TCP client → PortList
        ├─ PacketReceive()       → read startup packet
        └─ ConnStartup()
              ├─ be_recvauth()   → authenticate
              └─ BackendStartup()
                    ├─ FORK()
                    │    └─ child: DoExec() → execv(… "-P<fd>" …)
                    └─ parent: remember pid in BackendList
```

When a backend dies → `reaper` → `CleanupProc` (maybe kill peers + `reset_shared`).

---

## 3. External roster (names not defined in this file)

Tap a link to jump to the definition. Anything **`static`** above is *local*; these are *imported*.

### Types / constants (headers)

| Name | Where | Role |
|------|-------|------|
| `Port`, `PacketBuf`, `StartupInfo`, `MsgType`, `ARGV_SIZE`, `INVALID_SOCK`, `NON_BLOCKING` | [`libpq/pqcomm.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.h) | Socket + startup-packet shapes |
| `STARTUP_MSG`, `STARTUP_HBA_MSG` | same | Message-type enum values |
| `STATUS_OK` / `STATUS_ERROR` / … | [`include/postgres.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/include/postgres.h) | Return codes |
| `Dllist`, `Dlelem`, `DLNewList`, `DLAddHead`, … | [`lib/dllist.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/lib/dllist.h) | Doubly-linked list helpers |
| `DebugLvl`, `DataDir` (decl), paths | [`include/miscadmin.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/include/miscadmin.h) + [`utils/init/globals.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/utils/init/globals.c) | Globals |
| `IPCKey`, shm helpers | [`storage/ipc.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/storage/ipc.h) | Shared-memory keys |

### Functions (other `.c` files)

| Call in postmaster | Defined in | Does |
|--------------------|------------|------|
| `StreamServerPort` | [`libpq/pqcomm.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.c) | `socket`/`bind`/`listen` |
| `StreamConnection` | same | `accept` into a `Port` |
| `StreamClose` | same | close client fd |
| `PacketReceive` | [`libpq/pqpacket.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqpacket.c) | Read length-prefixed packet |
| `pq_getport` | [`libpq/pqcomm.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.c) | Default port from env / 5432 |
| `be_setauthsvc` / `be_recvauth` | [`libpq/auth.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/auth.c) | Auth setup / handshake |
| `EnableMemoryContext` | [`utils/mmgr/mcxt.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/utils/mmgr/mcxt.c) | Turn on Postgres memory contexts |
| `CreateSharedMemoryAndSemaphores` | [`storage/ipc/ipci.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/storage/ipc/ipci.c) | Create shm for backends |
| `SystemPortAddressCreateIPCKey` | [`storage/ipc/ipc.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/storage/ipc/ipc.c) | Port → IPC key |
| `exitpg` / `quasi_exitpg` | same `ipc.c` | Cleanup + exit (or cleanup without exit) |
| `ProcRemove` | [`storage/lmgr/proc.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/storage/lmgr/proc.c) | Drop process table entry |
| `FindBackend` / `ValidateBackend` | [`utils/init/findbe.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/utils/init/findbe.c) | Locate `postgres` binary path |
| `GetPGData` | [`utils/init/miscinit.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/utils/init/miscinit.c) | `$PGDATA` |
| `ValidPgVersion` | [`utils/init/magic.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/utils/init/magic.c) | Check `PG_VERSION` file |
| `NBuffers` | buffer manager | Shared buffer count |
| `IsPostmaster` | storage | Global flag “I am the listener” |
| `getopt` / `optarg` | libc | Argv parsing |
| `select` / `fork` / `execv` / `kill` / `waitpid` | libc / kernel | Networking & processes |

After `execv`, the child becomes [`tcop/postgres.c` → `PostgresMain`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/tcop/postgres.c) (same binary, different entry — see [`main/main.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/main/main.c)).

---

## 4. Slice walkthrough

Line numbers match
[`postmaster.c` @ `d31084e`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c)
(your tree may differ slightly if ported; the story is the same).

### Slice A — includes & `FORK` macro ([L35–L87](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L35-L87))

```c
#include "libpq/pqsignal.h"
#include <string.h>
#ifndef WIN32
#include <unistd.h>          /* Unix: fork, close, … */
#endif
…
#include "storage/ipc.h"
#include "libpq/pqcomm.h"    /* Port, StartupInfo */
…

#if defined(PORTNAME_irix5)
#define FORK() fork()
#else
#define FORK() vfork()       /* original: prefer vfork */
#endif
```

**Read as:** pull in OS + Postgres headers; pick `fork` vs `vfork` at compile time.

**Syntax:** `#include` and `#if` are preprocessor. The real call site later is just `FORK()`.

**Note for Linux learners:** the runnable snapshot in this repo may force `fork()` on Linux because `vfork` + `DoExec` stack use is unsafe — same *idea*, safer syscall.

---

### Slice B — file-local state ([L94–L164](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L94-L164))

```c
typedef struct bkend {
    int pid;
} Backend;

static Dllist*  BackendList;   /* children we spawned */
static Dllist*  PortList;      /* half-open client sockets */
static short    PostPortName = -1;
static int      ServerSock = INVALID_SOCK;

extern char *DataDir;          /* defined elsewhere */

static void pmdaemonize(void); /* forward declaration */
static int  ConnStartup(Port *port);
…
int ServerLoop(void);          /* public: not static */
int BackendStartup(…);
```

**Read as:** the postmaster keeps two lists and a listen socket. Forward declarations tell the compiler “these functions exist below” so order doesn’t matter.

**Syntax:**
- `static` at file scope = private to this `.c`.
- `extern` = “look in another object file.”
- Prototype `static void pmdaemonize(void);` — `void` in `()` means no arguments (old C style sometimes writes `pmdie()` with empty parens).

---

### Slice C — `PostmasterMain` entry ([L172–L359](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L172-L359))

This is what [`main.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/main/main.c) calls when `argv[0]` looks like `postmaster`.

```c
int
PostmasterMain(int argc, char *argv[])
{
    extern int NBuffers;
    extern bool IsPostmaster;
    …
    (void) umask((mode_t) 0077);     /* new files: owner-only */

    while ((opt = getopt(argc, argv, "a:B:b:D:dmM:no:p:Ss")) != EOF) {
        switch (opt) {
        case 'p': PostPortName = (short) atoi(optarg); break;
        case 'D': DataDir = optarg; break;
        …
        }
    }
    if (PostPortName == -1)
        PostPortName = pq_getport();

    IsPostmaster = true;
    if (!DataDir) DataDir = GetPGData();
    checkDataDir();

    status = StreamServerPort(hostName, PostPortName, &ServerSock);
    …
    EnableMemoryContext(TRUE);
    reset_shared(PostPortName);

    BackendList = DLNewList();
    PortList = DLNewList();

    signal(SIGINT, pmdie);
    signal(SIGCHLD, reaper);   /* child died → reaper */

    status = ServerLoop();
    ExitPostmaster(status != STATUS_OK);
}
```

**Read as:** parse flags → find data dir → create listen socket → create shared memory → install signal handlers → never return from `ServerLoop` until error/shutdown.

**Syntax notes:**
- `int argc, char *argv[]` — standard C main signature (`argv` is an array of string pointers).
- `optarg` — set by `getopt` to the argument of `-p`, `-D`, etc. (`extern` from libc).
- `&ServerSock` — pass address so `StreamServerPort` can **write** the fd into our variable.
- `signal(SIGCHLD, reaper)` — register function pointer `reaper` as handler.
- `status != STATUS_OK` — boolean expression passed as int to `ExitPostmaster`.

**Important flags**

| Flag | Effect |
|------|--------|
| `-p N` | Listen port |
| `-D path` | Data directory |
| `-B N` | Shared buffers (also appended to `ExtraOptions` for children) |
| `-S` | Daemonize (`pmdaemonize`) |
| `-n` | Don’t reinit shm after crash |
| `-s` | `SIGSTOP` peers instead of kill (for core dumps) |

---

### Slice D — `pmdaemonize` ([L361–L379](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L361-L379))

```c
static void
pmdaemonize()
{
    if (fork())
        exit(0);              /* parent exits; child continues */
    setsid();                 /* new session, no controlling tty */
    i = open(NULL_DEV, O_RDWR);
    dup2(i, 0); dup2(i, 1); dup2(i, 2);  /* stdin/out/err → /dev/null */
}
```

**Read as:** classic Unix “become a background daemon.”

**Syntax:** `if (fork())` — nonzero (parent) is true → parent exits; child sees `0` (false) and continues.

---

### Slice E — `ServerLoop` ([L399–L552](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L399-L552))

This is the heart. One `select` watches the **listen** socket and every **half-open** client still sending a startup packet.

```c
int
ServerLoop()
{
    fd_set rmask, basemask;
    FD_ZERO(&basemask);
    FD_SET(ServerSock, &basemask);   /* watch listen fd */

    for (;;) {
        memmove(&rmask, &basemask, sizeof(fd_set));
        nSelected = select(nSockets, &rmask, NULL, NULL, NULL);

        if (FD_ISSET(ServerSock, &rmask)) {
            ConnCreate(serverFd, &newFd);  /* accept */
            FD_SET(newFd, &basemask);      /* also watch new client */
        }

        for (curr = DLGetHead(PortList); curr; …) {
            Port *port = (Port*)DLE_VAL(curr);
            if (FD_ISSET(port->sock, &rmask)) {
                status = PacketReceive(port, &port->buf, NON_BLOCKING);
                switch (status) {
                case STATUS_OK:
                    ConnStartup(port);     /* auth + fork backend */
                    /*FALLTHROUGH*/
                case STATUS_INVALID:
                    … close & remove from PortList …
                case STATUS_NOT_DONE:
                    … partial read; wait for more …
                }
            }
        }
    }
}
```

**Read as:**
1. New connection on listen socket → `ConnCreate` → stay on `PortList` until startup packet complete.
2. Data on a client socket → `PacketReceive`.
3. Full packet → `ConnStartup` (then drop that socket from the postmaster’s watch set — the **backend** owns it after fork).

**Syntax:**
- `fd_set` + `FD_SET` / `FD_ISSET` — bitset of file descriptors for `select`.
- `(fd_set *) NULL` — explicit null pointer cast (no write-set / except-set / timeout).
- `DLE_VAL(curr)` — macro: get pointer stored in list element.
- `/*FALLTHROUGH*/` — after successful startup, also run the cleanup of the postmaster’s `Port` (connection handed off).

**Race note in comments:** they block `SIGCHLD` around list mutation because `reaper` also touches lists / `free` (non-reentrant).

---

### Slice F — `ConnCreate` ([L615–L638](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L615-L638))

```c
static int
ConnCreate(int serverFd, int *newFdP)
{
    Port *port = (Port *) calloc(1, sizeof(Port));
    status = StreamConnection(serverFd, port);  /* accept */
    if (status != STATUS_OK) {
        StreamClose(port->sock);
        free(port);
    } else {
        DLAddHead(PortList, DLNewElem(port));
        *newFdP = port->sock;   /* write fd back to caller */
    }
    return status;
}
```

**Syntax:** `int *newFdP` is an **out-parameter**. Caller passes `&newFd`; we store with `*newFdP = …`.

**External:** [`StreamConnection`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.c) does the real `accept`.

---

### Slice G — `ConnStartup` ([L554–L610](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L554-L610))

```c
static int
ConnStartup(Port *port)
{
    StartupInfo sp;
    PacketBuf *p = &port->buf;
    char *tmp = p->data;

    strncpy(sp.database, tmp, sizeof(sp.database)); tmp += …;
    strncpy(sp.user,     tmp, sizeof(sp.user));     tmp += …;
    /* options, execFile, tty likewise */

    msgType = ntohl(port->buf.msgtype);  /* network byte order → host */

    if (msgType == STARTUP_MSG && useHostBasedAuth)
        msgType = STARTUP_HBA_MSG;

    if (be_recvauth(msgType, port, namebuf, &sp) != STATUS_OK)
        return STATUS_ERROR;

    return BackendStartup(&sp, port, &pid);
}
```

**Read as:** unpack fixed-width fields from the packet buffer → authenticate → start backend.

**Syntax:**
- `ntohl` — “network to host long”; multi-byte ints on the wire are big-endian.
- `&sp` — pass address of local struct so callee can read fields.
- `useHostBasedAuth` — set at compile time via `#ifdef HBA` (see top of file).

**External:** [`be_recvauth`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/auth.c).

---

### Slice H — `BackendStartup` + `DoExec` ([L798–L1059](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L798-L1059))

```c
int
BackendStartup(StartupInfo *packet, Port *port, int *pidPtr)
{
    putenv("POSTPORT=…");
    putenv("POSTID=…");
    putenv("PG_USER=…");

    if ((pid = FORK()) == 0) {          /* CHILD */
        if (DoExec(packet, port->sock))
            … error …
        _exit(1);                       /* exec failed */
    }
    /* PARENT */
    if (pid < 0) return STATUS_ERROR;

    bn = calloc(1, sizeof(Backend));
    bn->pid = pid;
    DLAddHead(BackendList, DLNewElem(bn));
    *pidPtr = pid;
    return STATUS_OK;
}
```

```c
static int
DoExec(StartupInfo *packet, int portFd)
{
    char *av[ARGV_SIZE];
    int ac = 0;

    av[ac++] = Execfile;          /* path to postgres binary */
    av[ac++] = "-p";              /* “started by postmaster” */
    av[ac++] = "-Q";              /* or -dN for debug */
    sprintf(portbuf, "-P%d", portFd);
    av[ac++] = portbuf;           /* inherit this socket fd */
    av[ac++] = database_or_user;
    av[ac] = NULL;                /* argv must be NULL-terminated */

    return execv(av[0], av);      /* does not return on success */
}
```

**Read as:** child replaces itself with `postgres -p -P<fd> <dbname>`. The fd number is passed as text; the **open socket** survives `exec` because fds are inherited unless marked close-on-exec.

**Syntax:**
- `char *av[ARGV_SIZE]` — array of 64 `char*` (see crib sheet: “array of string pointers”).
- `av[ac] = (char *) NULL` — C convention: last argv element is null.
- `execv` returns only on failure (returns `-1`); success never returns.
- `_exit` vs `exit` — child uses `_exit` to avoid flushing parent’s stdio buffers twice after `vfork`/`fork`.

**Hand-off:** backend code path starts in [`PostgresMain`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/tcop/postgres.c); it parses `-P` and talks FE/BE on that socket.

---

### Slice I — death & cleanup ([L656–L789](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L656-L789))

```c
static void
reaper(int i)                    /* Linux: signal handlers take int */
{
    while ((pid = waitpid(-1, &status, WNOHANG)) > 0)
        CleanupProc(pid, status);
}

static void
CleanupProc(int pid, int exitstatus)
{
    if (!exitstatus) {
        /* clean exit: just drop from BackendList */
        ProcRemove(pid);
        return;
    }
    /* ugly death: signal all other backends, maybe reset_shared */
    kill(bp->pid, SendStop ? SIGSTOP : SIGUSR1);
    …
    if (ActiveBackends && Reinit) {
        quasi_exitpg();
        reset_shared(PostPortName);
    }
}
```

**Read as:** normal exit → bookkeeping. Crash → warn/stop peers and optionally rebuild shared memory so survivors aren’t using corrupt shm.

**Syntax:** `#if defined(PORTNAME_linux) … pmdie(int i)` — System V vs BSD signal-handler prototypes differed; Linux wants the `int` argument.

**External:** [`waitpid`](https://man7.org/linux/man-pages/man2/waitpid.2.html) (man page), [`ProcRemove`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/storage/lmgr/proc.c), [`quasi_exitpg`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/storage/ipc/ipc.c).

---

### Slice J — `reset_shared` / `checkDataDir` / `ExitPostmaster`

```c
static void
reset_shared(short port)
{
    key = SystemPortAddressCreateIPCKey((SystemPortAddress) port);
    CreateSharedMemoryAndSemaphores(key);
    ActiveBackends = FALSE;
}
```

```c
checkDataDir() {
    /* fopen("$DataDir/base/template1/pg_class") must succeed */
    /* ValidPgVersion(DataDir) */
}
```

**Read as:** shm is keyed off the listen port; data dir must already contain a bootstrapped `template1` (from `initdb`).

---

## 5. Suggested reading order (30–60 minutes)

1. Crib sheet (§1) — 5 min  
2. Story (§2) + external roster skim (§3) — 5 min  
3. Open the [GitHub file](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c); read **only** `PostmasterMain` with Slice C open — 10 min  
4. `ServerLoop` + `ConnCreate` (Slices E–F) — 15 min  
5. `ConnStartup` → `BackendStartup` → `DoExec` (G–H) — 15 min  
6. Skim `reaper` / `CleanupProc` (I) — 5 min  
7. Optional: jump to [`pqcomm.c` `StreamServerPort`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.c) and [`auth.c` `be_recvauth`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/auth.c)

Tiny modern sketch of the same control flow (not 1996 code):
[`learn/mini_postmaster.c`](https://github.com/asideofcode-dev/spiffe/blob/cursor/postgres-first-commit-430a/postgres/learn/mini_postmaster.c)

---

## 6. Quick “what does this token mean?” index

| Token in this file | Jump |
|--------------------|------|
| `#ifdef` / `#ifndef` | §1 Preprocessor |
| `static` | §1 Storage |
| `extern` | §1 Storage / Slice B |
| `typedef` | Slice B |
| `Port *` / `->` | §1 Pointers / [`pqcomm.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.h) |
| `FORK()` | Slice A + H |
| `select` / `fd_set` | Slice E |
| `getopt` / `optarg` | Slice C |
| `execv` / `av[]` | Slice H |
| `signal` / `reaper` | Slice C + I |
| `STATUS_OK` | [`postgres.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/include/postgres.h) |

Parent guide: [`READING.md`](https://github.com/asideofcode-dev/spiffe/blob/cursor/postgres-first-commit-430a/postgres/READING.md) (Path A).
