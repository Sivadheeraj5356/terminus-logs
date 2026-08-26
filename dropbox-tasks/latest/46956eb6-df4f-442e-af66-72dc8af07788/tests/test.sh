#!/bin/bash

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    exit 1
fi

set -uo pipefail
TEST_DIR="${TEST_DIR:-/tests}"
mkdir -p /logs/verifier

# Don't change anything below this line except the test file path or pytest flags.
pytest --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
