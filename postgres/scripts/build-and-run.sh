#!/usr/bin/env bash
# Build Postgres95 1.01 (first commit) as 32-bit and smoke-test the postmaster.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/src"
PREFIX="${PG95_PREFIX:-/tmp/pg95}"
PORT="${PG95_PORT:-15432}"

need() { command -v "$1" >/dev/null || { echo "missing: $1"; exit 1; }; }
need gcc; need gmake; need flex; need bison

if ! echo 'int main(void){return sizeof(void*)==4?0:1;}' \
    | gcc -m32 -x c -o /tmp/pg95-m32check - 2>/dev/null; then
  echo "Need a working gcc -m32 toolchain (gcc-multilib, libc6-dev-i386, libbsd-dev:i386)."
  exit 1
fi
/tmp/pg95-m32check || { echo "gcc -m32 did not produce a 32-bit binary"; exit 1; }

mkdir -p "$PREFIX"/{bin,data/files,lib,include}

echo "==> Building backend"
cd "$SRC/backend"
gmake -j1
gmake install || true
cp -f "$SRC/interfaces/libpq/pg_hba" "$PREFIX/data/pg_hba"
chmod 644 "$PREFIX/data/pg_hba"
install -c -m 555 obj/postgres "$PREFIX/bin/postgres"
ln -sfn postgres "$PREFIX/bin/postmaster"

echo "==> Building helpers"
cd "$SRC/bin/initdb" && gmake
cp -f obj/initdb "$PREFIX/bin/initdb" && chmod +x "$PREFIX/bin/initdb"
gcc -m32 -include "$SRC/backend/include/modern_compat.h" \
  -o "$PREFIX/bin/pg_id" "$SRC/bin/pg_id/pg_id.c"
cd "$SRC/bin/pg_version"
gmake || true
gcc -m32 -o "$PREFIX/bin/pg_version" obj/pg_version.o obj/magic.o
chmod +x "$PREFIX/bin/pg_id" "$PREFIX/bin/pg_version"

echo "==> Building frontend libpq"
cd "$SRC/interfaces/libpq"
gmake MKDIR=../../mk
cp -f obj/libpq.a "$PREFIX/lib/"
cp -f libpq-fe.h "$PREFIX/include/"

echo "==> initdb"
export PATH="$PREFIX/bin:$PATH" PGDATA="$PREFIX/data"
# Keep catalog files; wipe prior cluster data
find "$PGDATA" -mindepth 1 -maxdepth 1 ! -name files ! -name pg_hba -exec rm -rf {} +
initdb

echo "==> Starting postmaster on $PORT"
pkill -f "$PREFIX/bin/postmaster" 2>/dev/null || true
sleep 0.3
ipcrm -a 2>/dev/null || true
"$PREFIX/bin/postmaster" -p "$PORT" -D "$PGDATA" >"$PREFIX/postmaster.log" 2>&1 &
echo $! >"$PREFIX/postmaster.pid"
sleep 1
if ! kill -0 "$(cat "$PREFIX/postmaster.pid")" 2>/dev/null; then
  echo "postmaster failed to start:"; cat "$PREFIX/postmaster.log"; exit 1
fi

echo "==> Smoke query"
gcc -m32 \
  -I"$PREFIX/include" -I"$SRC/interfaces/libpq" \
  -I"$SRC/backend" -I"$SRC/backend/include" \
  -include "$SRC/backend/include/modern_compat.h" \
  -o "$PREFIX/bin/pg95-smoke" "$ROOT/scripts/smoke.c" \
  -L"$PREFIX/lib" -lpq -lbsd
export PGUSER="${PGUSER:-$(whoami)}"
"$PREFIX/bin/pg95-smoke" "$PORT"

echo
echo "OK — postmaster pid $(cat "$PREFIX/postmaster.pid") listening on $PORT"
echo "Log: $PREFIX/postmaster.log"
echo "Stop with: kill \$(cat $PREFIX/postmaster.pid)"
