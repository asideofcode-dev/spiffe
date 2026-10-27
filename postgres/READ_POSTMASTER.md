# Annotated reading helper — `postmaster.c`

Source (tap to open on phone):
[`src/backend/postmaster/postmaster.c` @ `d31084e`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c)

## What this file is for

In early Postgres, one program binary can run in three modes: **postmaster** (listener), **backend** (one client session), or **bootstrap** (initdb). This file implements the listener.

The postmaster’s job is deliberately narrow:

1. Open a TCP (or Unix-domain) **listen** socket.
2. Create **shared memory** and semaphores that all backends will attach to.
3. Wait for clients.
4. For each client: read a **startup packet**, authenticate, **fork** a child, **exec** the same binary as a backend, handing the connected socket across as `-P<fd>`.
5. When children die, clean up; if a child crashes messily, warn or stop its peers and maybe rebuild shared memory.

You do **not** need SQL knowledge to read this file. You *do* need a little C and a little Unix process/socket vocabulary. The rest of this guide teaches those as they appear.

**How to use this page:** keep the [GitHub file](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c) open in another tab. Read a slice here, then scroll to the matching lines there. Every important name that is *not* defined in `postmaster.c` has a link to where it *is* defined.

---

## 1. C crib sheet (for this file)

If you already know C, skim this and jump to §2. If you don’t, read it once before the slices — then come back when a token surprises you.

### 1.1 The preprocessor (`#…` lines)

Lines starting with `#` are handled **before** the real compiler runs. They edit the source text.

**`#include`**

```c
#include "libpq/pqcomm.h"   /* project header: quotes */
#include <stdio.h>          /* system header: angle brackets */
```

Think of this as “paste the contents of that file here.” Headers usually contain *declarations* (names and types) so this `.c` file can call functions or use structs defined elsewhere. The `"…"` form searches the project tree first; `<…>` searches the system include path (libc, etc.).

**`#ifdef` / `#ifndef` / `#if defined(…)` / `#else` / `#endif`**

```c
#ifndef WIN32
#include <unistd.h>
#endif
```

This is **not** a runtime `if`. At build time, either `WIN32` is defined as a macro or it isn’t. If it isn’t, the `#include <unistd.h>` line stays in the program; if it is, that line is deleted and never compiled.

That is why one source file can contain Windows *and* Unix code: each platform’s compiler only keeps its own branch. When you read on Linux, you can usually skip `#ifdef WIN32` … `#endif` blocks on a first pass.

**`#define`**

```c
#define FORK() fork()
```

Wherever the token `FORK()` appears later, the preprocessor replaces it with `fork()` before compiling. Macros can also take arguments and can be dangerous (no type checking); here it’s just a portable name for “create a child process.”

**Comments**

```c
/* this is a comment — the compiler ignores it */
```

Old Postgres style uses `/* … */` almost everywhere (not `//`).

### 1.2 `static`, `extern`, and who can see a name

C has a notion of **linkage**: which other files can refer to a name.

| Declaration | Who can use it |
|-------------|----------------|
| `static int ServerSock;` at file scope | Only code in *this* `.c` file |
| `static void pmdie(int);` | Only this `.c` can call `pmdie` |
| `int PostmasterMain(…)` (no `static`) | Other `.c` files can call it after linking |
| `extern char *DataDir;` | “`DataDir` lives in another `.c`; I’m just announcing it” |

**Why `static` matters here:** the postmaster keeps private lists (`BackendList`, `PortList`) and a listen socket (`ServerSock`). Marking them `static` means a random function in `pqcomm.c` cannot accidentally touch them — encapsulation without C++ classes.

**Why `extern` matters:** `DataDir` is a global string pointer actually defined in [`utils/init/globals.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/utils/init/globals.c). This file only *uses* it. The linker stitches the reference to the definition when building the binary.

**Forward declarations** look like:

```c
static void pmdaemonize(void);
```

That tells the compiler “a function with this signature exists later in the file,” so `PostmasterMain` can call `pmdaemonize` even though the body appears below. In modern C you’d often reorder functions instead; 1990s style loves prototypes at the top.

### 1.3 Types, structs, and `typedef`

```c
typedef struct bkend {
    int pid;     /* process id of backend */
} Backend;
```

A **struct** groups fields. `typedef … Backend` creates a short type name so you can write `Backend *bn` instead of `struct bkend *bn`.

Postgres also defines richer structs in headers, especially [`Port`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.h) (one client connection) and [`StartupInfo`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.h) (database name, user, options from the first client packet).

Common scalar types you’ll see:

- `int` — signed integer (pids, statuses, fds).
- `short` — smaller integer (port number stored in `PostPortName`).
- `char` — one byte; used for characters.
- `bool` — Postgres’s boolean typedef (often still an integer underneath in this era).

### 1.4 Pointers (the part that usually hurts)

A **pointer** holds the *address* of something else.

```c
char *progname;   /* points at a C string (or is NULL) */
Port *port;       /* points at a Port struct in memory */
int  *newFdP;     /* points at an int belonging to the caller */
```

| Expression | Meaning |
|------------|---------|
| `port->sock` | Field `sock` inside the struct that `port` points to |
| `*newFdP = 5` | Write `5` into the int that `newFdP` points at |
| `&ServerSock` | Address of the variable `ServerSock` |
| `NULL` | Pointer that deliberately points nowhere |

**Why pass `&ServerSock`?**  
`StreamServerPort(host, port, &ServerSock)` needs to *fill in* the listen file descriptor. C passes arguments by value, so if you passed `ServerSock` itself the callee would only get a copy. Passing the address lets the callee write into *your* variable.

**Why `(Port *) calloc(1, sizeof(Port))`?**  
`calloc` returns `void *` (untyped pointer) to zeroed heap memory. The cast tells the compiler “treat this as a `Port *`.” `sizeof(Port)` is how many bytes one `Port` needs.

**C strings:** there is no built-in string type. A string is a `char *` pointing at bytes ending in `'\0'`. Functions like `strcpy`, `strncpy`, `sprintf` write those bytes. Buffer overflows were (and are) easy — this codebase is from 1996 and is not a model of modern safety.

### 1.5 Control flow patterns in this file

**Infinite listen loop**

```c
for (;;) {
    /* … select, accept, handle … */
}
```

Same idea as `while (1)`. The postmaster is meant to run until a signal or fatal error.

**`getopt` loop**

```c
while ((opt = getopt(argc, argv, "a:B:b:D:…")) != EOF) {
    switch (opt) {
    case 'p': … break;
    case 'D': … break;
    }
}
```

`getopt` (libc) walks `argv`. A letter followed by `:` in the option string means “this flag takes an argument,” available in the global `optarg`. `EOF` (or `-1`) means “no more flags.”

**`switch` and fall-through**

```c
case STATUS_OK:
    ConnStartup(port);
    /*FALLTHROUGH*/
case STATUS_INVALID:
    /* close the port */
```

Normally each `case` ends with `break`. Without `break`, execution continues into the next `case`. Here that is intentional: after a successful startup, also run the cleanup that drops the connection from the postmaster’s list (the backend now owns the socket).

**Return codes**

Postgres often returns `STATUS_OK` (0) or `STATUS_ERROR` (-1), defined in [`postgres.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/include/postgres.h). Treating `0` as success matches Unix convention.

### 1.6 Processes, file descriptors, and signals (Unix words)

These are OS concepts the postmaster leans on heavily.

**Process**  
An OS-level running program with its own address space. The postmaster is one process; each backend is another.

**`fork` / `vfork`**  
Clone the current process. In the parent, the call returns the child’s process id (pid). In the child, it returns `0`. After fork, both continue from the same line — you almost always write `if (fork() == 0) { /* child */ } else { /* parent */ }`.

`vfork` is an older, more restricted variant used here via the `FORK()` macro for speed on some platforms. On modern Linux, `fork` is the safe choice when the child will soon call `exec` after touching stack data (as `DoExec` does). The learning snapshot in this repo may already force `fork()` on Linux for that reason; the *logic* you should learn is still “parent keeps listening; child becomes backend.”

**`execv`**  
Replace *this* process’s program image with another executable. File descriptors stay open across `exec` unless marked close-on-exec. That is the trick: the child still holds the client socket, then `execv`s into `postgres`, and passes the fd number as the text argument `-P42` so the new image knows which fd to use.

**File descriptor (fd)**  
A small integer the kernel uses for open files/sockets (`0` stdin, `1` stdout, `2` stderr, then 3, 4, …). `ServerSock` is the listen fd; each accepted client gets another fd.

**`select`**  
Block until one or more fds in a set become “ready” (e.g. readable). Lets one thread/process wait on the listen socket *and* many half-open clients without spinning.

**Signals**  
Software interrupts. `signal(SIGCHLD, reaper)` means “when a child process exits, call `reaper`.” `SIGINT` is Ctrl-C; the handler `pmdie` shuts the postmaster down.

**`waitpid`**  
After a child exits it becomes a *zombie* until the parent collects its exit status. `reaper` loops on `waitpid(-1, &status, WNOHANG)` to collect any number of dead children without blocking.

---

## 2. The story of the file

At a high level the control flow is:

```
PostmasterMain                          ← entry from main.c
  ├─ parse argv (-p, -D, -B, -S, …)
  ├─ checkDataDir()                     ← template1 must already exist
  ├─ StreamServerPort()                 ← socket/bind/listen
  ├─ reset_shared()                     ← create shm + semaphores
  ├─ BackendList / PortList = empty lists
  ├─ install signal handlers
  └─ ServerLoop()                       ← runs “forever”
        ├─ select(listen fd + pending clients)
        ├─ new connection? → ConnCreate() → PortList
        ├─ data on a client? → PacketReceive()
        └─ full startup packet? → ConnStartup()
              ├─ unpack StartupInfo
              ├─ be_recvauth()
              └─ BackendStartup()
                    ├─ putenv(POSTPORT, POSTID, PG_USER, …)
                    ├─ FORK()
                    │     child → DoExec() → execv(postgres, "-p", "-Pfd", db)
                    └─ parent → remember pid on BackendList

child exit → SIGCHLD → reaper() → CleanupProc()
              dirty exit → signal peers; maybe reset_shared()
```

Two lists are easy to confuse:

| List | Holds | Lifetime |
|------|-------|----------|
| `PortList` | Clients still sending the startup packet | Short — removed once the backend is started (or the attempt fails) |
| `BackendList` | Live backend pids | Until that backend exits |

The postmaster does **not** parse SQL. After `execv`, the child is a different logical program path (`PostgresMain` in [`tcop/postgres.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/tcop/postgres.c)).

---

## 3. External roster

Names below are **used** in `postmaster.c` but **defined** elsewhere. Tap through when a slice mentions them.

### 3.1 Types and constants

| Name | Defined in | Role |
|------|------------|------|
| `Port`, `PacketBuf`, `StartupInfo`, `MsgType` | [`libpq/pqcomm.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.h) | Connection + first-packet shapes |
| `ARGV_SIZE`, `INVALID_SOCK`, `NON_BLOCKING` | same | Buffer sizes / sentinel fd / read mode flag |
| `STARTUP_MSG`, `STARTUP_HBA_MSG` | same (`MsgType` enum) | “This packet starts a session” (optionally with host-based auth) |
| `STATUS_OK`, `STATUS_ERROR`, `STATUS_NOT_DONE`, … | [`include/postgres.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/include/postgres.h) | Standardized return codes |
| `Dllist`, `Dlelem`, `DLNewList`, `DLAddHead`, `DLGetHead`, … | [`lib/dllist.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/lib/dllist.h) | Doubly-linked list helpers |
| `DebugLvl`, path helpers | [`miscadmin.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/include/miscadmin.h) | Debug level and admin globals |
| `DataDir` (definition) | [`utils/init/globals.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/utils/init/globals.c) | Path to the data directory |
| `IPCKey` and friends | [`storage/ipc.h`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/storage/ipc.h) | Keys for SysV shared memory / semaphores |

### 3.2 Functions

| Call | Defined in | What it does for the postmaster |
|------|------------|----------------------------------|
| `StreamServerPort` | [`libpq/pqcomm.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.c) | `socket` → `bind` → `listen`; writes listen fd out |
| `StreamConnection` | same | `accept` a client into a `Port` |
| `StreamClose` | same | Close a client socket |
| `PacketReceive` | [`libpq/pqpacket.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqpacket.c) | Read a length-prefixed packet (can be partial) |
| `pq_getport` | [`libpq/pqcomm.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.c) | Default port from environment / compiled default |
| `be_setauthsvc` / `be_recvauth` | [`libpq/auth.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/auth.c) | Choose auth method; run the handshake |
| `EnableMemoryContext` | [`utils/mmgr/mcxt.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/utils/mmgr/mcxt.c) | Turn on Postgres’s memory-context allocator |
| `CreateSharedMemoryAndSemaphores` | [`storage/ipc/ipci.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/storage/ipc/ipci.c) | Create the shared segment backends attach to |
| `SystemPortAddressCreateIPCKey` | [`storage/ipc/ipc.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/storage/ipc/ipc.c) | Derive an IPC key from the listen port |
| `exitpg` / `quasi_exitpg` | same `ipc.c` | Run process-exit callbacks; `quasi_` skips actually exiting |
| `ProcRemove` | [`storage/lmgr/proc.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/storage/lmgr/proc.c) | Remove a backend from the shared process table |
| `FindBackend` / `ValidateBackend` | [`utils/init/findbe.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/utils/init/findbe.c) | Locate / sanity-check the `postgres` executable path |
| `GetPGData` | [`utils/init/miscinit.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/utils/init/miscinit.c) | Resolve `$PGDATA` if `-D` wasn’t given |
| `ValidPgVersion` | [`utils/init/magic.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/utils/init/magic.c) | Check the `PG_VERSION` file under the data dir |
| `getopt` / `optarg` | libc | Command-line flag parsing |
| `select`, `fork`, `execv`, `kill`, `waitpid`, `dup2`, … | libc / kernel | Networking and process control |

**After `execv`:** the new image enters via [`main/main.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/main/main.c) and, because of `-p`, ends up in [`PostgresMain`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/tcop/postgres.c) — not back in `PostmasterMain`.

---

## 4. Slice walkthrough

Line numbers refer to
[`postmaster.c` @ `d31084e`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c).
If you are reading a slightly ported copy in this repo, small details (especially `FORK`) may differ; the architecture is the same.

---

### Slice A — Includes and the `FORK` macro

[Lines 35–87](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L35-L87)

```c
#include "libpq/pqsignal.h"   /* signal() wrappers / substitutes */
#include <string.h>
#include <stdlib.h>
#ifndef WIN32
#include <unistd.h>           /* fork, close, setsid, … */
#endif
…
#include "storage/ipc.h"
#include "libpq/libpq.h"
#include "libpq/auth.h"
#include "libpq/pqcomm.h"     /* Port, StartupInfo, MsgType */
#include "miscadmin.h"
#include "lib/dllist.h"
…

#if defined(PORTNAME_irix5)
#define FORK() fork()
#else
#define FORK() vfork()
#endif
```

**What’s going on**

The first block pulls in libc and OS headers. The second block pulls in Postgres headers that declare the types and functions this file will call. Without those includes, the compiler would not know what a `Port *` is or that `StreamServerPort` exists.

The `FORK()` macro is an abstraction over “create a child.” Historically many Unixes preferred `vfork` when the child would quickly `exec`, because it avoided copying the address space. The child of `vfork` must be careful what it does before `exec`; `DoExec` builds argv on the stack, which is one reason modern Linux ports often redefine this to `fork()`.

**What to do while reading**

1. Skim includes; don’t open every header yet.  
2. Note which headers sound like networking (`pqcomm`, `auth`) vs storage (`ipc`) vs lists (`dllist`).  
3. Remember: `#ifndef WIN32` means “Linux/Unix path for us.”

---

### Slice B — File-local state and prototypes

[Lines 94–164](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L94-L164)

```c
typedef struct bkend {
    int pid;
} Backend;

static Dllist*  BackendList;
static Dllist*  PortList;

static short    PostPortName = -1;
static short    ActiveBackends = FALSE;
static int      NextBackendId = MAXINT;
static char    *progname = (char *) NULL;

extern char    *DataDir;

static char     Execfile[MAXPATHLEN] = "";
static int      ServerSock = INVALID_SOCK;
static char     ExtraOptions[ARGV_SIZE] = "";

static int      Reinit = 1;
static int      SendStop = 0;

#ifdef HBA
static int useHostBasedAuth = 1;
#else
static int useHostBasedAuth = 0;
#endif

static void pmdaemonize(void);
static int  ConnStartup(Port *port);
…
int ServerLoop(void);
int BackendStartup(StartupInfo *packet, Port *port, int *pidPtr);
```

**What’s going on**

This is the postmaster’s private notebook:

- `BackendList` — “which children did I start?” used when cleaning up.
- `PortList` — “which clients are mid-handshake?”
- `PostPortName` — TCP port (or name) we listen on; `-1` means “not set yet.”
- `ServerSock` — the listen file descriptor once created (`INVALID_SOCK` is `-1`).
- `Execfile` — filesystem path of the backend binary to `execv`.
- `ExtraOptions` — string of extra flags from `-o` / `-B` to pass through to children.
- `Reinit` / `SendStop` — policy when a backend dies badly (`-n` and `-s`).
- `useHostBasedAuth` — compile-time default from `#ifdef HBA`.

`NextBackendId` counts down from a large number; each new backend gets a distinct id via the `POSTID` environment variable. You don’t need the historical “why MAXINT” answer to follow the code — just notice ids are assigned and passed to children.

**Syntax to notice**

- Every `static` here is file-private.  
- `ServerLoop` and `BackendStartup` are *not* `static` — other translation units could call them (and they are part of the conceptual public API of this file).  
- `(char *) NULL` is an explicit null pointer cast; today people often write plain `NULL`.

---

### Slice C — `PostmasterMain`: startup of the listener

[Lines 172–359](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L172-L359)

This is the function [`main.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/main/main.c) calls when the program is running *as* the postmaster.

#### C.1 Secure defaults and hostname

```c
progname = argv[0];
(void) umask((mode_t) 0077);

if (!(hostName = getenv("PGHOST"))) {
    if (gethostname(hostbuf, MAXHOSTNAMELEN) < 0)
        (void) strcpy(hostbuf, "localhost");
    hostName = hostbuf;
}
```

`umask(0077)` means newly created files/directories won’t be group- or world-accessible — important for a database server that creates lock files and such.

`getenv("PGHOST")` reads an environment variable. If unset, fall back to this machine’s hostname, or `"localhost"`. `hostName` later feeds `StreamServerPort`.

`(void)` before a call means “I know this returns a value; I’m ignoring it on purpose” — silences some compiler warnings.

#### C.2 Parsing flags with `getopt`

```c
while ((opt = getopt(argc, argv, "a:B:b:D:dmM:no:p:Ss")) != EOF) {
    switch (opt) {
    case 'p':
        PostPortName = (short) atoi(optarg);
        break;
    case 'D':
        DataDir = optarg;
        break;
    case 'B':
        NBuffers = atol(optarg);
        strcat(ExtraOptions, " -B ");
        strcat(ExtraOptions, optarg);
        break;
    …
    }
}
```

Read the option string as a mini-language: `p:` means `-p` takes an argument; `S` means `-S` is a boolean flag with no argument.

Important flags for learning:

| Flag | Effect |
|------|--------|
| `-p N` | Listen on port N |
| `-D path` | Data directory |
| `-B N` | Shared buffer count; also forwarded to backends via `ExtraOptions` |
| `-b path` | Explicit backend executable |
| `-d [level]` | Debug verbosity |
| `-o '…'` | Extra backend options |
| `-S` | Daemonize (detach from terminal) |
| `-n` | On crash: do *not* reinitialize shared memory |
| `-s` | On crash: `SIGSTOP` peers (so you can collect core dumps) instead of the usual “please die” signal |

`NBuffers` and `IsPostmaster` are `extern` globals defined in other files; setting `IsPostmaster = true` later tells the rest of the system “shared memory should be created, not merely attached.”

#### C.3 Data directory and backend binary

```c
if (PostPortName == -1)
    PostPortName = pq_getport();

IsPostmaster = true;

if (!DataDir)
    DataDir = GetPGData();

checkDataDir();

if (!Execfile[0] && FindBackend(Execfile, argv[0]) < 0) {
    fprintf(stderr, "%s: could not find backend to execute...\n", argv[0]);
    exit(1);
}
```

Order of operations matters: you must know where `$PGDATA` is and that it looks like a real cluster (`checkDataDir` opens `…/base/template1/pg_class` and checks `PG_VERSION`) before you start accepting clients. `FindBackend` locates the `postgres` executable to `execv` later — often next to the `postmaster` symlink/binary.

#### C.4 Listen socket and shared memory

```c
status = StreamServerPort(hostName, PostPortName, &ServerSock);
if (status != STATUS_OK) {
    fprintf(stderr, "%s: cannot create stream port\n", progname);
    exit(1);
}

EnableMemoryContext(TRUE);
reset_shared(PostPortName);

BackendList = DLNewList();
PortList = DLNewList();
```

`StreamServerPort` (in [`pqcomm.c`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.c)) is the real `socket`/`bind`/`listen`. On success, `ServerSock` holds the listen fd.

`reset_shared` creates the shared memory segment and semaphores keyed off the port number. Backends will attach to the same key. Empty `Dllist`s start with no clients and no children.

#### C.5 Signals and entering the loop

```c
if (silentflag)
    pmdaemonize();

signal(SIGINT, pmdie);
signal(SIGCHLD, reaper);
signal(SIGHUP, pmdie);
signal(SIGTERM, pmdie);
…

status = ServerLoop();
ExitPostmaster(status != STATUS_OK);
```

From here, normal life is inside `ServerLoop`. Handlers run *asynchronously* when signals arrive — that is why comments elsewhere worry about races between `reaper` and list updates.

**Checkpoint:** In your own words: what has to be true before `ServerLoop` runs? (listen fd open, shm created, data dir valid, signal handlers installed.)

---

### Slice D — `pmdaemonize`: detach from the terminal

[Lines 361–379](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L361-L379)

```c
static void
pmdaemonize()
{
    int i;

    if (fork())
        exit(0);                 /* parent exits */

    if (setsid() < 0) {          /* child: new session */
        perror("cannot disassociate from controlling TTY");
        exit(1);
    }
    i = open(NULL_DEV, O_RDWR);  /* usually /dev/null */
    dup2(i, 0);
    dup2(i, 1);
    dup2(i, 2);
    close(i);
}
```

**What’s going on**

Classic “run as a daemon” recipe:

1. `fork` and exit the parent so the caller (shell) thinks the command finished.  
2. `setsid` so the child is not tied to the old terminal.  
3. Point stdin/stdout/stderr at `/dev/null` so accidental prints don’t fail or write to a gone tty.

**Syntax:** `if (fork())` uses the fact that the parent sees a nonzero pid (true) and the child sees `0` (false).

Only runs when you passed `-S`.

---

### Slice E — `ServerLoop`: the forever event loop

[Lines 399–552](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L399-L552)

This is the most important function to understand slowly.

#### E.1 Preparing the fd set

```c
int serverFd = ServerSock;
fd_set rmask, basemask;
…

nSockets = ServerSock + 1;
FD_ZERO(&basemask);
FD_SET(ServerSock, &basemask);
```

An `fd_set` is a bitset of file descriptors. `basemask` is the long-lived set of fds we care about. Initially it only contains the listen socket. As startup-in-progress clients appear, their fds are added; when finished, they are removed.

`nSockets` for `select` must be **one more than** the highest fd number watched.

#### E.2 Blocking in `select`

```c
for (;;) {
    memmove((char *) &rmask, (char *) &basemask, sizeof(fd_set));
    nSelected = select(nSockets, &rmask,
                       (fd_set *) NULL,
                       (fd_set *) NULL,
                       (struct timeval *) NULL);
    if (nSelected < 0) {
        if (errno == EINTR)
            continue;          /* interrupted by signal; retry */
        … error …
    }
```

Each loop iteration copies `basemask` into `rmask` because `select` *modifies* the set to show which fds are ready. A `NULL` timeout means “wait forever.” `EINTR` means a signal (often `SIGCHLD`) interrupted the wait — not a fatal error.

#### E.3 New connection on the listen socket

```c
if (FD_ISSET(ServerSock, &rmask)) {
    if (ConnCreate(serverFd, &newFd) == STATUS_OK) {
        if (newFd >= nSockets)
            nSockets = newFd + 1;
        FD_SET(newFd, &basemask);   /* watch this client too */
    }
    …
}
```

`ConnCreate` accepts the connection and puts a `Port` on `PortList`. The postmaster does **not** fork yet — it still needs the startup packet (user, database, …).

#### E.4 Readable client: receive packet and maybe start backend

```c
status = PacketReceive(port, &port->buf, NON_BLOCKING);
switch (status) {
case STATUS_OK:
    ConnStartup(port);
    ActiveBackends = TRUE;
    /*FALLTHROUGH*/
case STATUS_INVALID:
    /* done with this port — close and remove from PortList */
    …
case STATUS_NOT_DONE:
    /* partial read; keep port on the list and wait for more bytes */
    …
case STATUS_BAD_PACKET:
    /* hostile/confused client — drop */
    …
case STATUS_ERROR:
    return STATUS_ERROR;
}
```

[`PacketReceive`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqpacket.c) understands the length-prefixed layout of this era’s FE/BE packets. Because TCP is a byte stream, one `read` might not return the whole packet — `STATUS_NOT_DONE` means “keep this `Port` around.”

On `STATUS_OK`, `ConnStartup` authenticates and forks. Then fall-through closes the postmaster’s copy of the bookkeeping for that handshake. The *socket itself* is still open in the child (and briefly in the parent until closed — read carefully around `StreamClose`; the hand-off model is “child inherits fd, parent stops selecting on it”).

**Mental model:** `ServerLoop` is a tiny event-driven server: one process, many fds, no threads.

**Checkpoint:** Explain what is on `basemask` after one client connects but before its startup packet finishes.

---

### Slice F — `ConnCreate`: accept into a `Port`

[Lines 615–638](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L615-L638)

```c
static int
ConnCreate(int serverFd, int *newFdP)
{
    Port *port;

    if (!(port = (Port *) calloc(1, sizeof(Port)))) {
        fprintf(stderr, "%s: ConnCreate: malloc failed\n", progname);
        ExitPostmaster(1);
    }

    if ((status = StreamConnection(serverFd, port)) != STATUS_OK) {
        StreamClose(port->sock);
        free(port);
    } else {
        DLAddHead(PortList, DLNewElem(port));
        *newFdP = port->sock;
    }
    return status;
}
```

**What’s going on**

1. Allocate a zeroed `Port` on the heap.  
2. [`StreamConnection`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.c) calls `accept` and fills in `port->sock` and address fields.  
3. On success, push onto `PortList` and write the new fd into the caller’s variable via `*newFdP`.

**Syntax:** `int *newFdP` is an out-parameter. Failure paths free memory so the postmaster doesn’t leak a `Port` per failed accept.

---

### Slice G — `ConnStartup`: unpack, authenticate, start child

[Lines 554–610](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L554-L610)

```c
static int
ConnStartup(Port *port)
{
    StartupInfo sp;
    PacketBuf *p = &port->buf;
    char *tmp = p->data;

    sp.database[0] = '\0';
    … /* clear other fields */

    strncpy(sp.database, tmp, sizeof(sp.database));
    tmp += sizeof(sp.database);
    strncpy(sp.user, tmp, sizeof(sp.user));
    tmp += sizeof(sp.user);
    /* options, execFile, tty similarly */

    msgType = ntohl(port->buf.msgtype);

    if (!sp.user[0]) {
        fprintf(stderr, "%s: ConnStartup: no user name specified\n", progname);
        return STATUS_ERROR;
    }

    if (msgType == STARTUP_MSG && useHostBasedAuth)
        msgType = STARTUP_HBA_MSG;

    if (be_recvauth(msgType, port, namebuf, &sp) != STATUS_OK)
        return STATUS_ERROR;

    if (BackendStartup(&sp, port, &pid) != STATUS_OK)
        return STATUS_ERROR;

    return STATUS_OK;
}
```

**What’s going on**

The startup packet’s payload is a sequence of **fixed-size** fields laid out in order (database, user, options, …). The code advances `tmp` by each field’s size. This is brittle but easy to implement — characteristic of the era.

`ntohl` converts the message type from network byte order (big-endian on the wire) to host byte order so comparisons like `msgType == STARTUP_MSG` work on every CPU.

[`be_recvauth`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/auth.c) implements the authentication conversation for this connection. On success, `BackendStartup` creates the child.

**Checkpoint:** The postmaster still has not looked at any SQL. It only knows user, database name, options, and that auth succeeded.

---

### Slice H — `BackendStartup` and `DoExec`: fork + exec

[Lines 798–1059](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L798-L1059)

#### H.1 Environment for the child

```c
sprintf(envEntry[0], "POSTPORT=%d", PostPortName);
putenv(envEntry[0]);
sprintf(envEntry[1], "POSTID=%d", NextBackendId);
putenv(envEntry[1]);
sprintf(envEntry[2], "PG_USER=%s", packet->user);
putenv(envEntry[2]);
if (!getenv("PGDATA")) {
    sprintf(envEntry[3], "PGDATA=%s", DataDir);
    putenv(envEntry[3]);
}
```

The backend learns “which postmaster / which id / which user / which data dir” through the environment. (Comments in the code even say this ought to be a proper message — env vars were the pragmatic choice.)

#### H.2 Fork

```c
if ((pid = FORK()) == 0) {     /* child */
    if (DoExec(packet, port->sock))
        fprintf(stderr, "… execv failed …");
    _exit(1);
}

/* parent */
if (pid < 0)
    return STATUS_ERROR;
```

Child returns `0` from `FORK()` and calls `DoExec`. If `execv` fails, `DoExec` returns and the child prints an error then `_exit(1)`. Using `_exit` avoids running `atexit` hooks / flushing stdio buffers that may still be shared in subtle ways after `vfork`.

Parent sees `pid > 0` on success, or `pid < 0` if fork itself failed.

#### H.3 Parent bookkeeping

```c
bn = (Backend *) calloc(1, sizeof(Backend));
bn->pid = pid;
DLAddHead(BackendList, DLNewElem(bn));
NextBackendId -= 1;
*pidPtr = pid;
return STATUS_OK;
```

The postmaster must remember the child so `CleanupProc` can find it later.

#### H.4 Building `argv` for `execv`

```c
av[ac++] = execbuf;                 /* path to executable */
av[ac++] = "-p";                    /* means “I am a backend under postmaster” */
if (DebugLvl > 1)
    av[ac++] = debugbuf;            /* e.g. -d2 */
else
    av[ac++] = "-Q";                /* quieter */

sprintf(portbuf, "-P%d", portFd);
av[ac++] = portbuf;                 /* which fd holds the client socket */

split_opts(av, &ac, argbuf);        /* extra options split on spaces */
av[ac++] = dbbuf;                   /* database name (or user if db empty) */
av[ac] = (char *) NULL;

return execv(av[0], av);
```

**This is the hand-off contract:**

| Piece | Meaning |
|-------|---------|
| `Execfile` | Path of the same postgres binary |
| `-p` | “Started by postmaster” (not a solo backend) |
| `-P<fd>` | Client socket file descriptor number |
| final arg | Database name to open |

`split_opts` mutates a string, inserting `'\0'` over spaces, and stores pointers into `av` — a classic C argv-building trick. `av` must end with `NULL` or `execv` misbehaves.

On success, `execv` **does not return**. The process is now whatever `main` does with those arguments — eventually [`PostgresMain`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/tcop/postgres.c).

**Checkpoint:** Why pass the fd as *text* (`"-P5"`) instead of somehow “sending” the socket? Because `exec` replaces memory, but inherited fds remain open; the new program only needs to know *which number* to use.

---

### Slice I — `reaper` and `CleanupProc`: when backends die

[Lines 656–789](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/postmaster/postmaster.c#L656-L789)

```c
static void
reaper(int i)    /* Linux prototype includes the signal number */
{
    int status, pid;
    while ((pid = waitpid(-1, &status, WNOHANG)) > 0)
        CleanupProc(pid, status);
}
```

`WNOHANG` means “don’t block if no child is ready.” The loop reaps *all* currently dead children — important if several exit before the postmaster runs the handler.

```c
static void
CleanupProc(int pid, int exitstatus)
{
    if (!exitstatus) {
        /* clean exit: remove from BackendList, ProcRemove(pid), return */
        …
        return;
    }

    /* dirty exit: signal every other backend, clear lists, maybe reset shm */
    sig = SendStop ? SIGSTOP : SIGUSR1;
    kill(bp->pid, sig);
    …
    if (ActiveBackends == TRUE && Reinit) {
        quasi_exitpg();
        reset_shared(PostPortName);
    }
}
```

**Design idea:** a backend that exits with status 0 is normal (client disconnected cleanly enough). A nonzero status means something ugly happened — shared memory may be inconsistent — so the postmaster tells peers to exit quickly (`SIGUSR1` is special-cased elsewhere to mean “die without the usual cleanup path”) or stops them for debugging (`-s`). Then it may rebuild shared memory so *future* backends start clean.

`ActiveBackends` + `Reinit` avoid resetting shm repeatedly for the same failure wave.

**Syntax:** On Linux, signal handlers are declared `void handler(int)`. Other platforms in this file use `void handler()`. That’s why you see `#if defined(PORTNAME_linux)` around `pmdie` / `reaper` / `dumpstatus`.

---

### Slice J — Shared reset, data-dir check, exit

```c
static void
reset_shared(short port)
{
    IPCKey key = SystemPortAddressCreateIPCKey((SystemPortAddress) port);
    CreateSharedMemoryAndSemaphores(key);
    ActiveBackends = FALSE;
}
```

Same port → same IPC key → backends know where to attach. Called at postmaster start and after some crash cleanups.

```c
checkDataDir() {
    /* fopen("$DataDir/base/template1/pg_class", "r") must work */
    /* ValidPgVersion(DataDir) */
}
```

The postmaster refuses to start if `initdb` hasn’t created a usable cluster. That failure mode is much clearer than accepting clients and dying inside the first backend.

```c
ExitPostmaster(status) {
    if (ServerSock != INVALID_SOCK)
        close(ServerSock);
    exitpg(status);
}
```

Closes the listen socket and runs Postgres’s exit machinery ([`exitpg`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/storage/ipc/ipc.c)).

---

## 5. Suggested study plan

Aim for understanding, not memorizing line numbers.

| Session | Do this | You should be able to explain |
|---------|---------|-------------------------------|
| 1 (~20–30 min) | §1 crib sheet + §2 story | What `static`, pointers, `fork`/`exec`, and `select` mean *in this file* |
| 2 (~30–40 min) | Slice C with the GitHub file open | Everything that happens before the listen loop |
| 3 (~40 min) | Slices E–G | How a TCP accept becomes an authenticated `StartupInfo` |
| 4 (~30 min) | Slice H | Exact argv/env hand-off to the backend |
| 5 (~20 min) | Slice I | Why a crashed backend can kill peers / reset shm |
| Optional | [`pqcomm.c` `StreamServerPort`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/pqcomm.c), [`auth.c` `be_recvauth`](https://github.com/postgres/postgres/blob/d31084e9d1118b25fd16580d9d8c2924b5740dff/src/backend/libpq/auth.c), [`learn/mini_postmaster.c`](https://github.com/asideofcode-dev/spiffe/blob/cursor/postgres-first-commit-430a/postgres/learn/mini_postmaster.c) | Same ideas without 1996 density |

---

## 6. Token → section index

| When you see… | Read |
|---------------|------|
| `#ifdef` / `#ifndef` / `#define` | §1.1 |
| `static` / `extern` / prototypes | §1.2, Slice B |
| `typedef` / `struct` | §1.3 |
| `*` / `->` / `&` / `NULL` | §1.4 |
| `getopt` / `switch` / `FALLTHROUGH` | §1.5, Slices C & E |
| `fork` / `vfork` / `execv` / fds | §1.6, Slice H |
| `select` / `fd_set` | §1.6, Slice E |
| `signal` / `waitpid` / `reaper` | §1.6, Slice I |
| `Port` / `StartupInfo` / `STATUS_*` | §3.1 |
| `StreamServerPort` / `PacketReceive` / `be_recvauth` | §3.2 |
| Overall call graph | §2 |

Parent path guide: [`READING.md`](https://github.com/asideofcode-dev/spiffe/blob/cursor/postgres-first-commit-430a/postgres/READING.md) (Path A).

**This helper on GitHub:**
[`READ_POSTMASTER.md`](https://github.com/asideofcode-dev/spiffe/blob/cursor/postgres-first-commit-430a/postgres/READ_POSTMASTER.md)
