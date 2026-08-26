#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ] || [ ! -d /app ]; then
  echo "Error: verifier must run from a configured task working directory with /app available." >&2
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

TEST_DIR="${TEST_DIR:-/tests}"
if [ ! -d "$TEST_DIR" ]; then
  echo "Error: verifier test directory is missing: $TEST_DIR" >&2
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

export PYTHONSAFEPATH=1
export PYTHONDONTWRITEBYTECODE=1
cd "$TEST_DIR"

set +e
pytest --ctrf /logs/verifier/ctrf.json test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
