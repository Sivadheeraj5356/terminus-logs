#!/usr/bin/env bash
# Seed a tiny demo: one employee with a couple of logged hours blocks.
set -euo pipefail
BIN=/app/crosspay
"$BIN" init
"$BIN" add-employee alice --rate 7500000
"$BIN" log-hours alice 40 --now 1700000000
"$BIN" log-hours alice 8 --now 1700086400
echo "gross:"
"$BIN" gross alice
