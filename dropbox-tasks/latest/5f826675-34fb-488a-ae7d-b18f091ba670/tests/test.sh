#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
# Default to failure up front so an early error can never leave the reward
# file missing; the block below overwrites it once pytest has run.
echo 0 > /logs/verifier/reward.txt

TEST_DIR="${TEST_DIR:-/tests}"

# pytest and pytest-json-ctrf are pre-installed in the image (offline verifier).
python -m pytest --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
