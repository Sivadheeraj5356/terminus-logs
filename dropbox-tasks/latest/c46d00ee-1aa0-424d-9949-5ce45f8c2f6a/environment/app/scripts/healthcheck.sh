#!/bin/bash
set -eu
BIN="${BIN:-/app/target/release/metrics-cli}"
OUT="${OUT:-/tmp/metrics-health.txt}"
rm -f "$OUT"
"$BIN" --health > "$OUT"
grep -q metrics-factory-ok "$OUT"
