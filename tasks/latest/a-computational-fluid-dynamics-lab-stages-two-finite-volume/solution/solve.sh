#!/bin/bash
set -euo pipefail
cp /solution/model_correct.mzn /app/model.mzn
solution=$(minizinc --solver chuffed /app/model.mzn /app/instance.dzn)
printf '%s\n' "$solution"
case "$solution" in *----------*) ;; *) echo "ERROR: no solution" >&2; exit 1 ;; esac
