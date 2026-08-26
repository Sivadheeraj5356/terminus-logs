#!/bin/bash
# Canonical verifier runner — do not add a trailing exit.
set -uo pipefail

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set"
    mkdir -p /logs/verifier
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

mkdir -p /logs/verifier

# Default reward is failure; the pass path below overwrites it only on a clean pytest run.
echo 0 > /logs/verifier/reward.txt

TEST_DIR="${TEST_DIR:-/tests}"

# pytest + pytest-json-ctrf must be pre-installed in the image (never install here)
cd "$TEST_DIR" && python3 -m pytest -x --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -rA
status=$?
if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
