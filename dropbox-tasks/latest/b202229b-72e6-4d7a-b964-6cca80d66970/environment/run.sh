#!/usr/bin/env bash
set -uo pipefail
cd /app
if [ ! -f /app/out/Main.class ] || [ /app/Main.java -nt /app/out/Main.class ]; then
  javac -d /app/out /app/Main.java >/dev/null 2>&1 || exit 3
fi
exec java -cp /app/out Main "$@"
