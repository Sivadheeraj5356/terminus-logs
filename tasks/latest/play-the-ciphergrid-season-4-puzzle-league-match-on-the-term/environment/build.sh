#!/usr/bin/env bash
set -euo pipefail
cd /app/app
mkdir -p /app/bin /app/var
zig build-exe src/main.zig \
  -O ReleaseSafe \
  -lc \
  -femit-bin=/app/bin/cipherleague
chmod 0755 /app/bin/cipherleague
test -x /app/bin/cipherleague
