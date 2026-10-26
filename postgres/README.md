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

Start with `src/backend/main/`, `src/backend/tcop/`, and `src/backend/access/heap/` if you want a readable path through query dispatch and heap access.

## Runnable sketch

The 1996 sources do not build on modern Linux. For a working listen→accept→fork→exec demo, see [`learn/`](learn/).

## License

Original copyright notices apply (University of California / Postgres95). See headers in individual source files.
