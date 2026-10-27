# PostgreSQL — first commit (Postgres95 1.01)

Snapshot of the **very first commit** in the official [postgres/postgres](https://github.com/postgres/postgres) Git history, checked in here as a learning sandbox for C and early database internals.

| | |
|---|---|
| **Commit** | [`d31084e9d1118b25fd16580d9d8c2924b5740dff`](https://github.com/postgres/postgres/commit/d31084e9d1118b25fd16580d9d8c2924b5740dff) |
| **Message** | Postgres95 1.01 Distribution - Virgin Sources |
| **Date** | 1996-07-09 |
| **Author** | Marc G. Fournier |

This is the root of the converted CVS history — the “virgin” Postgres95 1.01 sources. Later PostgreSQL evolution is not included.

## Layout

```
postgres/src/
  backend/      # server: access methods, executor, optimizer, parser, storage, …
  bin/          # client tools (psql precursors, etc.)
  interfaces/   # libpq and related client libraries
  tutorial/     # sample SQL / C tutorial material
  test/         # regression tests
  tools/        # build / maintenance helpers
```

**Reading order:** see **[`READING.md`](https://github.com/asideofcode-dev/spiffe/blob/cursor/postgres-first-commit-430a/postgres/READING.md)** — Paths A–F with tap-friendly GitHub links into the first commit (`d31084e`) on mobile.

**C + `postmaster.c`:** annotated slice guide for newcomers — **[`READ_POSTMASTER.md`](https://github.com/asideofcode-dev/spiffe/blob/cursor/postgres-first-commit-430a/postgres/READ_POSTMASTER.md)** (`#ifdef`, `static`, externals linked).

Quick start without the full guide: `src/backend/main/`, `src/backend/tcop/`, and `src/backend/access/heap/` for query dispatch and heap access.

## Build & run the real postmaster

See **[`BUILD.md`](BUILD.md)**. Short version:

```bash
# needs gcc-multilib / 32-bit libc (Postgres95 is 32-bit)
./postgres/scripts/build-and-run.sh
```

That builds a 32-bit `postmaster`, runs `initdb`, starts it on port 15432, and
runs a smoke `SELECT` via the vintage libpq.

For a tiny listen→accept→fork→exec teaching sketch (no database), see [`learn/`](learn/).

## License

Original copyright notices apply (University of California / Postgres95). See headers in individual source files.
