#!/bin/bash
set -uo pipefail
trap 'sync /logs/verifier 2>/dev/null || true; sleep 0.25' EXIT

mkdir -p /logs/verifier && echo 0 > /logs/verifier/reward.txt

TEST_DIR="${TEST_DIR:-/tests}"
if [ "$PWD" = "/" ]; then
  echo "run tests from a workspace with /workspace mounted" >&2
  exit 1
fi

python3 -m pytest --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -rA
exit_code=$?

if [ "$exit_code" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
