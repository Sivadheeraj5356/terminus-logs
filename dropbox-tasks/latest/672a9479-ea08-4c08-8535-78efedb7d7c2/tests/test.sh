#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
cd /app/repo
/usr/local/go/bin/go build -o /app/repo/bin/trace_blur ./cmd/trace_blur
pytest -q -rA /tests/test_outputs.py
status=$?
if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
