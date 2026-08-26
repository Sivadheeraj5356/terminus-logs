#!/bin/bash
set -euo pipefail
src=/solution/solution.cpp
if [ ! -f "$src" ]; then
  src="$(cd "$(dirname "$0")" && pwd)/solution.cpp"
fi
cp "$src" /app/src/main.cpp
make -C /app
