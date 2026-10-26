# Building & running Postgres95 1.01 on modern Linux

This tree is the **first Git commit** of PostgreSQL (1996). It was written for
32-bit Unix. On a modern x86_64 Linux host you can still compile and run it
with a few portability shims and **`-m32`**.

## Prerequisites

```bash
sudo apt-get install -y \
  build-essential gcc-multilib flex bison \
  libbsd-dev libbsd-dev:i386 libc6-dev-i386
```

## One-shot build & smoke test

```bash
./postgres/scripts/build-and-run.sh
```

Or manually:

```bash
# 1. Backend (produces /tmp/pg95/bin/{postgres,postmaster})
cd postgres/src/backend
gmake -j1
gmake install
# install also needs:
cp ../interfaces/libpq/pg_hba /tmp/pg95/data/pg_hba

# 2. Helpers
cd ../bin/initdb && gmake && cp obj/initdb /tmp/pg95/bin/
gcc -m32 -include ../backend/include/modern_compat.h \
  -o /tmp/pg95/bin/pg_id ../bin/pg_id/pg_id.c
gcc -m32 -o /tmp/pg95/bin/pg_version \
  ../bin/pg_version/obj/pg_version.o ../bin/pg_version/obj/magic.o
# (build those .o via: cd ../bin/pg_version && gmake  # ignore -lpq link failure)

# 3. Frontend libpq
cd ../interfaces/libpq && gmake MKDIR=../../mk
cp obj/libpq.a /tmp/pg95/lib/
cp libpq-fe.h /tmp/pg95/include/

# 4. Initialize & run
export PATH=/tmp/pg95/bin:$PATH PGDATA=/tmp/pg95/data
initdb
postmaster -p 15432 -D "$PGDATA" &
```

## What we patched for modern GCC/glibc

| Change | Why |
|--------|-----|
| `Makefile.custom` + `PORTNAME=linux` + `-m32` | 1996 code assumes 32-bit pointers/Datums |
| `modern_compat.h` force-included | prototypes, `union semun`, headers |
| `indexam.c` `GET_*_PROCEDURE` | ANSI `##` cannot paste `->` |
| `elog.c` / `exc.c` use `strerror` | `sys_errlist` removed from glibc |
| Linux uses `fork()` not `vfork()` | `DoExec` is unsafe under `vfork` |
| Duplicate symbol fixes (`DataDir`, `reldesc`, `yylval`) | modern linkers reject common-block dups |
| ELF `dlopen` instead of GNU `dld` | `dld` is long gone |

Config lives in `src/Makefile.custom` (install prefix defaults to `/tmp/pg95`).

## Talk to it

Postgres95’s wire protocol is **not** compatible with modern `psql`. Use the
bundled libpq from this tree (see `scripts/smoke.c`) or the old `monitor`/`psql`
clients once built against that libpq.
