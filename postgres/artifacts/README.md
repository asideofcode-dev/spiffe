# Run artifacts (Postgres95 protocol probe)

Captured from a live 32-bit postmaster on `localhost:15432`.

| File | What it is |
|------|------------|
| `initdb.log` | Bootstrap of `template1` |
| `postmaster-highlights.log` | Accept → fork/exec → WARNs → cleanup |
| `protocol-probe.log` | Full libpq client probe transcript |
| `libpq-trace.log` | Raw FE/BE letter stream (`Q`/`T`/`D`/`C`/`E`) |

Re-run: build the tree, start postmaster, then compile/run `scripts/protocol-probe.c` against this libpq.
