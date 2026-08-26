#!/bin/bash
set -uo pipefail

export PATH="/usr/local/cargo/bin:/opt/verifier-venv/bin:/opt/verifier-scripts:${PATH}"
export CARGO_INCREMENTAL=0

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

if [ -d /tests/verifier-fixtures ]; then
    rm -rf /opt/verifier-fixtures
    mkdir -p /opt/verifier-fixtures
    cp -a /tests/verifier-fixtures/. /opt/verifier-fixtures/
fi

bash /app/scripts/rebuild-assay-ledger.sh
if [ $? -ne 0 ]; then
    echo "FAIL: rebuild failed"
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

TEST_DIR="${TEST_DIR:-/tests}"

set +e
python3 -m pytest -rA -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py"
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
