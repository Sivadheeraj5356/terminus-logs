#!/usr/bin/env bash
set -euo pipefail

ROOT="/app/environment"
BUILD="/app/build"
ENGINE="$BUILD/demo_engine"
OUT="/app/output"

cmake -S "$ROOT" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" -j2
mkdir -p "$OUT"

printf '%-4s %12s %18s %12s\n' token ledger_tail scalar_near addon_aux
for token in Q0 Q1 Q2 Q3 Q4 Q5 Q6 Q7 Q8; do
  path="$OUT/matrix_${token}.json"
  "$ENGINE" emit "$token" "$path"
  ledger="$(sed -n 's/.*"ledger_tail":\([0-9]*\).*/\1/p' "$path")"
  near="$(sed -n 's/.*"scalar_near":\([0-9.e+-]*\).*/\1/p' "$path")"
  addon="$(sed -n 's/.*"addon_aux":\([0-9.e+-]*\).*/\1/p' "$path")"
  printf '%-4s %12s %18s %12s\n' "$token" "$ledger" "$near" "$addon"
done

first="$OUT/matrix_Q5_rerun_a.json"
second="$OUT/matrix_Q5_rerun_b.json"
"$ENGINE" emit Q5 "$first"
"$ENGINE" emit Q5 "$second"
if ! cmp -s "$first" "$second"; then
  echo "emit_matrix: Q5 is not deterministic across consecutive runs" >&2
  exit 1
fi

echo "emit_matrix: all scene tokens emitted; run bash /tests/test.sh for exact reference gate" >&2
