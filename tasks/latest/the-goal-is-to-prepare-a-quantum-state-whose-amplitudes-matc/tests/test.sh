#!/usr/bin/env bash
VD=/logs/verifier
mkdir -p "$VD"
DIR="$(cd "$(dirname "$0")" && pwd)"
rustc -O /app/submission.rs -o /app/submission 2> "$VD/compile.log"
if [ ! -x /app/submission ]; then
  echo "submission.rs failed to compile"
  cat "$VD/compile.log"
fi
python3 -m pytest "$DIR/test_encode.py" -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
