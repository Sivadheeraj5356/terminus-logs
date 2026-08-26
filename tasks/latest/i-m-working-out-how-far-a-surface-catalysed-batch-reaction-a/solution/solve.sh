#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
gcc -O2 -std=c11 -o /tmp/tracer-yield-oracle "$ROOT/invert.c" -lm
/tmp/tracer-yield-oracle /app/reactor
