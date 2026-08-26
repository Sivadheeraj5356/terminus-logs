#!/bin/bash

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    exit 1
fi

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

set +e
TEST_DIR="${TEST_DIR:-/tests}" bash -c 'export PATH="/opt/verifier/bin:${PATH}"; export PYTHONPATH="/app/harness:${TEST_DIR}:${PYTHONPATH:-}"; cd /app && npm run build && python3 -m pytest -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py" -rA'
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
