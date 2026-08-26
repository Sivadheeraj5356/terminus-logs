#!/usr/bin/env bash
set -uo pipefail

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set."
  mkdir -p /logs/verifier
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

mkdir -p /logs/verifier
python3 -m pytest /tests/test_outputs.py -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
