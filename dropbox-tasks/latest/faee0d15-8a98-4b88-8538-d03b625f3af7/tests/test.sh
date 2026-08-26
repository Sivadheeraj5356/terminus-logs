#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
printf '{"results":{"tool":{"name":"pytest"},"summary":{"tests":0,"passed":0,"failed":0},"tests":[]}}\n' > /logs/verifier/ctrf.json

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    exit 1
fi

export PATH="/usr/local/go/bin:${PATH}"
/opt/verifier/bin/pytest -o cache_dir=/tmp/pytest-cache --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA --tb=short
exit_code=$?

if [ "$exit_code" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
