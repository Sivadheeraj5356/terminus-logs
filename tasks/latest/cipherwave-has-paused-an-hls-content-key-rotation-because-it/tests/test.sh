#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
TEST_DIR="${TEST_DIR:-/tests}"
export APP_DIR="${APP_DIR:-/app}"
result=1
trap 'exit "$result"' EXIT
/opt/test-venv/bin/python -m pytest -p no:cacheprovider "$TEST_DIR/test_outputs.py" -rA --tb=short
result=$?
if [ "$result" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
