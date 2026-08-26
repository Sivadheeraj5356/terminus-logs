#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier

if [ "$PWD" = "/" ] || [ ! -d "$PWD" ]; then
    echo "Error: No working directory set. Set a WORKDIR in your Dockerfile." >&2
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

TEST_DIR="${TEST_DIR:-/tests}"

python3 -m pytest -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -rA
rc=$?

if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
