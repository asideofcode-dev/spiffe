# Reading guide — Postgres95 1.01 (first Git commit)

This tree is small enough to read with intent, and large enough that wandering
randomly is slow. Use one of the paths below depending on what you want to
learn. Paths are ordered; each step names **files**, **symbols to search**, and
**what you should understand before moving on**.

Snapshot provenance: see [`README.md`](README.md). To run the server while you
read: [`BUILD.md`](BUILD.md). Live FE/BE probe notes: [`artifacts/`](artifacts/).

---

## Map of the tree (one screen)

```
postgres/
  src/
    backend/           # the server (and postmaster — same binary)
      main/            # argv[0] dispatcher → postmaster | bootstrap | backend
      postmaster/      # listen, accept, auth, fork/exec backends
      libpq/           # BE-side sockets, packets, auth
      tcop/            # PostgresMain: read query → parse → plan → execute
      parser/          # SQL → parse trees (gram.y, scan.l)
      optimizer/       # parse tree → plan
      executor/        # run the plan
      access/          # heap, btree, hash, rtree, xact
      storage/         # buffers, files, shm/semaphores, locks
      catalog/         # system catalogs + bootstrap .bki generators
      commands/        # CREATE/DROP/COPY/VACUUM… utility commands
      utils/           # mmgr, elog, fmgr, caches, init
      nodes/           # List, Node tagging, copy/equal/out/read
      port/linux/      # OS glue (dynloader, machine.h)
    interfaces/libpq/  # FE-side client library (PQsetdb / PQexec)
    bin/               # initdb, psql, monitor, …
    tutorial/          # SQL + small C examples from the era
  learn/               # tiny listen→accept→fork→exec sketch (modern C)
  artifacts/           # captured initdb / postmaster / wire-trace logs
```

One binary, three modes (`main/main.c`):

| `argv[0]` / flag | Entry | Role |
|------------------|-------|------|
| name ends with `postmaster` | `PostmasterMain` | TCP listener, spawns children |
| `-boot` | `BootstrapMain` | initdb catalog load |
| otherwise | `PostgresMain` | backend session (also what children become after `execv`) |

---

## Path A — C + networking (shortest; start here if new to sockets)

**Goal:** see `socket` → `bind` → `listen` → `select` → `accept` → `fork` → `execv`
without drowning in SQL.

| # | Read | Focus |
|---|------|--------|
| 1 | [`learn/mini_postmaster.c`](learn/mini_postmaster.c) + [`learn/mini_backend.c`](learn/mini_backend.c) | Same control flow in ~200 lines of modern C. Run `learn/Makefile`. |
| 2 | [`src/backend/main/main.c`](src/backend/main/main.c) | How one binary becomes postmaster vs backend. |
| 3 | [`src/backend/postmaster/postmaster.c`](src/backend/postmaster/postmaster.c) | `PostmasterMain` → `StreamServerPort` → `ServerLoop` → `ConnCreate` → `ConnStartup` → `BackendStartup` → `DoExec`. |
| 4 | [`src/backend/libpq/pqcomm.c`](src/backend/libpq/pqcomm.c) | `StreamServerPort`, `StreamConnection`, `StreamOpen` — real `socket`/`bind`/`listen`/`accept`/`connect`. |
| 5 | [`src/backend/libpq/pqpacket.c`](src/backend/libpq/pqpacket.c) | `PacketReceive` / `PacketSend` — length-prefixed packets, peek then read. |
| 6 | [`src/backend/libpq/pqcomm.h`](src/backend/libpq/pqcomm.h) | `Port`, `PacketBuf`, `StartupInfo`, `MsgType`. |
| 7 | [`src/backend/libpq/auth.c`](src/backend/libpq/auth.c) | `be_recvauth` — what happens between startup packet and fork. |
| 8 | [`src/interfaces/libpq/fe-connect.c`](src/interfaces/libpq/fe-connect.c) | Client side of the same handshake (`PQsetdb`). |

**Checkpoint:** You can narrate, without looking, how a TCP connection becomes a
child process with `-P<fd>` and why the postmaster closes its copy of that fd.

**Optional:** compare with [`artifacts/postmaster-highlights.log`](artifacts/postmaster-highlights.log).

---

## Path B — One query end-to-end (the “database” path)

**Goal:** follow `SELECT * FROM probe_demo` from client bytes to heap tuples.

### B1. Client

| # | Read | Focus |
|---|------|--------|
| 1 | [`src/interfaces/libpq/fe-connect.c`](src/interfaces/libpq/fe-connect.c) | Build `StartupInfo`, send `STARTUP_MSG`. |
| 2 | [`src/interfaces/libpq/fe-exec.c`](src/interfaces/libpq/fe-exec.c) | `PQexec`: send `Q` + SQL; read `T`/`D`/`C`/`E`. |
| 3 | [`artifacts/libpq-trace.log`](artifacts/libpq-trace.log) + [`artifacts/protocol-probe.log`](artifacts/protocol-probe.log) | What those letters looked like on a live run. |

### B2. Postmaster handoff

| # | Read | Focus |
|---|------|--------|
| 4 | Path A steps 3–7 (skim if already done) | Until `execv(postgres, "-p", "-P<fd>", dbname)`. |
| 5 | [`src/backend/tcop/postgres.c`](src/backend/tcop/postgres.c) — `PostgresMain` | Parse `-p` / `-P`, attach to the inherited socket, enter the query loop. |

### B3. Parse → plan → execute

| # | Read | Focus |
|---|------|--------|
| 6 | [`src/backend/parser/parser.c`](src/backend/parser/parser.c), peek `gram.y` / `scan.l` | SQL text → parse tree nodes. Don’t memorize the grammar; note the entry points. |
| 7 | [`src/backend/nodes/`](src/backend/nodes/) (`nodes.h`, `pg_list.h`, `makefuncs.c`) | Tagged `Node` structs + `List` — the lingua franca between stages. |
| 8 | [`src/backend/optimizer/plan/planner.c`](src/backend/optimizer/plan/planner.c) | Parse tree → `Plan`. Skim `path/` only after this file makes sense. |
| 9 | [`src/backend/tcop/pquery.c`](src/backend/tcop/pquery.c) | `ProcessQuery` — glue from plan to executor. |
| 10 | [`src/backend/executor/execMain.c`](src/backend/executor/execMain.c) | `ExecutorStart` / `ExecutorRun` / `ExecutorEnd`. |
| 11 | [`src/backend/executor/nodeSeqscan.c`](src/backend/executor/nodeSeqscan.c) | Simplest plan node: sequential scan. |

### B4. Tuples on disk

| # | Read | Focus |
|---|------|--------|
| 12 | [`src/backend/access/heap/heapam.c`](src/backend/access/heap/heapam.c) | `heap_getnext`, `heap_insert`, … — relation access API. |
| 13 | [`src/backend/storage/buffer/bufmgr.c`](src/backend/storage/buffer/bufmgr.c) | How pages get into shared buffers. |
| 14 | [`src/backend/storage/smgr/md.c`](src/backend/storage/smgr/md.c) | File-backed storage manager (magnetic disk). |
| 15 | [`src/backend/storage/page/bufpage.c`](src/backend/storage/page/bufpage.c) | Page layout helpers. |

**Checkpoint:** For a sequential `SELECT`, you can name the function chain from
`PQexec` to `heap_getnext` and back to a `D` message.

---

## Path C — Process model & shared memory

**Goal:** understand why postmaster exists and what children share.

| # | Read | Focus |
|---|------|--------|
| 1 | Path A (postmaster spawn) | Children are separate processes. |
| 2 | [`src/backend/storage/ipc/ipci.c`](src/backend/storage/ipc/ipci.c) | `CreateSharedMemoryAndSemaphores` — called once by postmaster. |
| 3 | [`src/backend/storage/ipc/ipc.c`](src/backend/storage/ipc/ipc.c) | SysV shm/sem wrappers. |
| 4 | [`src/backend/storage/ipc/shmem.c`](src/backend/storage/ipc/shmem.c) | Attach/lookup of named shared structures. |
| 5 | [`src/backend/storage/lmgr/lock.c`](src/backend/storage/lmgr/lock.c) + [`proc.c`](src/backend/storage/lmgr/proc.c) | Lock table living in shared memory; wait queues. |
| 6 | [`src/backend/utils/init/postinit.c`](src/backend/utils/init/postinit.c) | Backend attach when started under postmaster (`POSTPORT`, etc.). |
| 7 | [`src/backend/postmaster/postmaster.c`](src/backend/postmaster/postmaster.c) — `reaper` / `CleanupProc` | What happens when a backend dies. |

**Checkpoint:** You know what is per-process vs shared, and why a crashed backend
doesn’t take down the listener.

---

## Path D — Catalogs & initdb

**Goal:** see how an empty data directory becomes `template1`.

| # | Read | Focus |
|---|------|--------|
| 1 | [`src/bin/initdb/initdb.sh`](src/bin/initdb/initdb.sh) | Shell orchestration; feeds `.bki` into `postgres -boot`. |
| 2 | [`artifacts/initdb.log`](artifacts/initdb.log) | What that looked like on a successful run. |
| 3 | [`src/backend/bootstrap/bootstrap.c`](src/backend/bootstrap/bootstrap.c) | Bootstrap mode entry / relation creation. |
| 4 | [`src/backend/catalog/`](src/backend/catalog/) — start with `pg_class.h`, `pg_attribute.h`, `pg_proc.h` | Catalog shapes; DATA() lines become `.bki`. |
| 5 | [`src/backend/catalog/genbki.sh`](src/backend/catalog/genbki.sh) | Header → `global1.bki` / `local1_template1.bki`. |
| 6 | [`src/backend/utils/cache/relcache.c`](src/backend/utils/cache/relcache.c) | How backends cache relation descriptors after boot. |
| 7 | [`src/backend/utils/init/magic.c`](src/backend/utils/init/magic.c) | `PG_VERSION` / `SetPgVersion`. |

**Checkpoint:** You can explain why initdb runs `postgres -boot` three times and
what “nailing” a catalog relation means at a high level.

---

## Path E — Utility commands (DDL)

**Goal:** see how `CREATE TABLE` differs from `SELECT` in the codepaths.

| # | Read | Focus |
|---|------|--------|
| 1 | [`src/backend/tcop/utility.c`](src/backend/tcop/utility.c) | Dispatch for non-SELECT statements. |
| 2 | [`src/backend/commands/creatinh.c`](src/backend/commands/creatinh.c) | Create relation (inheritance-aware naming of the era). |
| 3 | [`src/backend/catalog/heap.c`](src/backend/catalog/heap.c) | `heap_create` / catalog updates for a new relation. |
| 4 | [`src/backend/commands/remove.c`](src/backend/commands/remove.c) | DROP. |
| 5 | [`src/backend/commands/copy.c`](src/backend/commands/copy.c) | COPY — touches FE/BE copy protocol (`P`/`T`/`D`/`C` plus copy lines). |

Pair with [`artifacts/protocol-probe.log`](artifacts/protocol-probe.log) (`CREATE` /
`INSERT` / `UPDATE` / `DELETE` sections).

---

## Path F — Frontend only

**Goal:** learn the client API without the backend.

| # | Read | Focus |
|---|------|--------|
| 1 | [`src/interfaces/libpq/libpq-fe.h`](src/interfaces/libpq/libpq-fe.h) | Public surface: `PQsetdb`, `PQexec`, `PGresult`, status enums. |
| 2 | [`src/interfaces/libpq/fe-connect.c`](src/interfaces/libpq/fe-connect.c) | Connection + startup packet. |
| 3 | [`src/interfaces/libpq/fe-exec.c`](src/interfaces/libpq/fe-exec.c) | Query execution and result parsing. |
| 4 | [`src/interfaces/libpq/fe-auth.c`](src/interfaces/libpq/fe-auth.c) | Client auth helpers. |
| 5 | [`scripts/protocol-probe.c`](scripts/protocol-probe.c) or [`scripts/smoke.c`](scripts/smoke.c) | Minimal modern-ish drivers against this libpq. |
| 6 | [`src/test/examples/`](src/test/examples/) | Period client samples (`testlibpq.c`, …). |

---

## How to read a single `.c` file in this tree

1. **Header comment** — often states the module’s job better than the filename.
2. **Includes** — `postgres.h` / `c.h` pull the world; then local headers name the
   real dependencies.
3. **Types first** — structs at the top or in the matching `.h`.
4. **Search the entry symbol** you care about (`StreamServerPort`, `PostgresMain`,
   `heap_insert`); ignore static helpers until that function calls them.
5. **`elog(WARN|FATAL|NOTICE, …)`** — runtime error paths; useful breadcrumbs.
6. **Skip port `#ifdef` forests** on the first pass (`WIN32`, `PORTNAME_*`).

Useful shared headers:

- [`src/backend/include/c.h`](src/backend/include/c.h) — C dialect helpers, `CppConcat`, basic types
- [`src/backend/include/postgres.h`](src/backend/include/postgres.h) — core typedefs, `MAXPGPATH`, …
- [`src/backend/include/miscadmin.h`](src/backend/include/miscadmin.h) — globals (`IsPostmaster`, debug, paths)

---

## Suggested order if you only have a few evenings

| Evening | Path | Outcome |
|---------|------|---------|
| 1 | **A** (learn/ + postmaster + pqcomm) | Networking + process model in your head |
| 2 | **B1–B3** through `execMain` | Query pipeline sketched |
| 3 | **B4** heap + buffer | Where rows live |
| 4 | **C** or **D** | Shared memory *or* initdb/catalogs |
| later | **E** / **F** / optimizer `path/` | Deepen as curiosity dictates |

---

## Files you can skip (at first)

| Area | Why wait |
|------|----------|
| `backend/tioga/` | Research/extension glue; not on the main query path |
| `backend/commands/_deadcode/` | Explicitly untested “version” rules |
| Most of `backend/port/*` except `linux/` | Other Unix ports |
| Full `optimizer/path/*.c` | After `planner.c` + one join path file |
| `regex/` internals | Treat as a library |
| Kerberos bits in `auth.c` | Unless you care about auth variants |

---

## Pair reading with running

```bash
# tiny networking sketch
cd postgres/learn && make && make run

# real postmaster + smoke SELECT
./postgres/scripts/build-and-run.sh

# broader FE/BE probe (after postmaster is up)
# compile scripts/protocol-probe.c against /tmp/pg95 libpq — see BUILD.md
```

Keep [`artifacts/protocol-probe.log`](artifacts/protocol-probe.log) open beside
`fe-exec.c` and `pqcomm.h` — the letter stream (`Q`/`T`/`D`/`C`/`E`) is the
protocol cheat sheet for this era.
