#!/usr/bin/env bash
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
cd /app

python3 -m pytest -o cache_dir=/tmp/pytest_cache /tests/test_outputs.py -v -rA --tb=short --ctrf /logs/verifier/ctrf.json
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
