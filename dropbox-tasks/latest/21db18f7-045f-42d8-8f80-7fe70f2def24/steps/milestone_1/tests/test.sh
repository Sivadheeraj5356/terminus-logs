#!/bin/bash
# tests/test.sh — Milestone 1 verifier

set -euo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
printf '%s\n' '{"version":"1.0.0","results":{"summary":{"tests":0,"passed":0,"failed":0,"pending":0,"skipped":0,"other":0}}}}' > /logs/verifier/ctrf.json

if [ "$PWD" = "/" ]; then
    echo 0 > /logs/verifier/reward.txt
    echo "Error: No working directory set."
    exit 1
fi

cd /tests || {
    echo 0 > /logs/verifier/reward.txt
    exit 1
}

source /opt/test-venv/bin/activate
export PYTHONPATH="/opt/verifier-reference:${PYTHONPATH:-}"

set +e
pytest test_m1.py -v --tb=short -rA \
    -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
