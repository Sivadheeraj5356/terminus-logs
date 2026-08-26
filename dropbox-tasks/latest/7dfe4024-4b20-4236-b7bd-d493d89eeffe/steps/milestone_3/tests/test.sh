#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
TEST_DIR="${TEST_DIR:-/tests}"

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

/opt/verifier-venv/bin/python -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json -rA \
  "$TEST_DIR/test_m3.py"
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi