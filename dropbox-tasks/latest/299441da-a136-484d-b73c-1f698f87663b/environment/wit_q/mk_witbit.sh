#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="$ROOT/libkq_wit.so"
SRC="$ROOT/witbit.c"
CC="${CC:-gcc}"
"$CC" -shared -fPIC -O2 -o "$OUT" "$SRC"
echo "built $OUT"
