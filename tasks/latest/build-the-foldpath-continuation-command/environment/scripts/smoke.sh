#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

make -C "$ROOT" clean all
"$ROOT/build/foldmodel-check" --model "$ROOT/examples/cubic.model" --control "$ROOT/examples/standard.control" >/dev/null
"$ROOT/build/foldmodel-check" --control "$ROOT/examples/cautious.control" --model "$ROOT/examples/coupled.model" >/dev/null
"$ROOT/build/foldmodel-check" --model "$ROOT/examples/bratu.model" --control "$ROOT/examples/precise.control" >/dev/null

if [ -x "$ROOT/build/foldpath" ]; then
    python3 "$ROOT/scripts/check_contract.py"
fi
