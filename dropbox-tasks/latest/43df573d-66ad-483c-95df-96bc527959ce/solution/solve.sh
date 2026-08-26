#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
SRC=/solution/main_correct.jl
[ -f "$SRC" ] || SRC="$DIR/main_correct.jl"
cp "$SRC" /app/environment/attack/main.jl
python3 /app/environment/samples/local_check.py julia /app/environment/attack/main.jl
echo "oracle solver installed"
