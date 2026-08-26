#!/bin/bash
# run.sh -- assemble the postings tool and run it over a tape.
#
#   run.sh [INPUT_BIN] [OUTPUT_TXT]
#
# With no arguments the batch reads /app/data/records.bin and writes
# /app/data/report.txt. The assembled program is left at /app/build/tape.fs.
set -euo pipefail

IN="${1:-/app/data/records.bin}"
OUT="${2:-/app/data/report.txt}"

bash /app/build/assemble.sh
rm -f "$OUT"
gforth /app/build/tape.fs "$IN" "$OUT"
