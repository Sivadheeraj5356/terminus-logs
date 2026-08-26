#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
echo '{"results":{"tool":{"name":"pytest"},"summary":{"tests":0,"passed":0,"failed":0,"pending":0,"skipped":0,"other":0,"start":0,"stop":0},"tests":[]}}' > /logs/verifier/ctrf.json

cd /app
export PATH="/usr/local/go/bin:/tmp:/usr/local/bin:${PATH:-}"
export RUNTIME_ROOT="${RUNTIME_ROOT:-/app}"
export RUNTIME_BIN="${RUNTIME_BIN:-/tmp/runtime}"
export TB3_APP_ROOT="${TB3_APP_ROOT:-$RUNTIME_ROOT}"
TEST_DIR="${TEST_DIR:-/tests}"

# Rebuild from current sources before scoring.
go build -o "${RUNTIME_BIN}" ./cmd/runtime

set +e
python3 -m pytest \
    -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json \
    "${TEST_DIR}/test_outputs.py" \
    -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
