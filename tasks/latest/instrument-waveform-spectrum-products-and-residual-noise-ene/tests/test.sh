#!/bin/bash
# Accepted-corpus verifier shape — deps in environment/Dockerfile only.
set -uo pipefail

export PATH="/opt/verifier-venv/bin:/opt/verifier-scripts:${PATH}"

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
printf '%s\n' '{"version":"1.0.0","results":{"summary":{"tests":0,"passed":0,"failed":0,"pending":0,"skipped":0,"other":0}}}' > /logs/verifier/ctrf.json

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

cd /app || {
    echo 0 > /logs/verifier/reward.txt
    exit 1
}

TEST_DIR="${TEST_DIR:-/tests}"

set +e
python3 -m pytest -rA -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py"
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
