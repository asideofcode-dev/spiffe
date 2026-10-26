# Mini postmaster (runnable sketch)

The real Postgres95 tree in `../src` is from **1996** and does not build cleanly on modern Linux (old C dialect, missing `flex`, ancient headers).

This folder is a tiny stand-in so you can **watch the same control flow work**:

```
listen  →  select  →  accept  →  fork  →  execv(backend, "-P<fd>")
```

## Build & run

```bash
cd postgres/learn
make
./mini_postmaster 15432
```

In another terminal (Python works if you don't have `nc`):

```bash
python3 -c 'import socket;s=socket.create_connection(("127.0.0.1",15432));s.sendall(b"hello\n");print(s.recv(1024).decode());print(s.recv(1024).decode());s.close()'
```

Or one-shot:

```bash
make run
```

## Map to real Postgres95

| This demo | Real files |
|-----------|------------|
| `stream_server_port` | `libpq/pqcomm.c` → `StreamServerPort` |
| `select` + `accept` | `postmaster/postmaster.c` → `ServerLoop` / `ConnCreate` |
| `fork` + `execv … -P%d` | `BackendStartup` / `DoExec` |
| `mini_backend` `-P` parse | `tcop/postgres.c` postmaster-started path |
