#!/bin/bash
# assemble.sh -- build the runnable postings tool from the vendored kit.
#
# The tool is assembled by placing the vendored record-format library ahead of
# the decoder so the decoder can use its field accessors, and writing the result
# to /app/build/tape.fs, which gforth then runs.
set -euo pipefail

KIT=/app/vendor/reckit
OUT=/app/build/tape.fs

: > "$OUT"
cat "$KIT/recfmt.fs" >> "$OUT"
printf '\n' >> "$OUT"
cat /app/build/decode.fs >> "$OUT"
