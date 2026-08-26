#!/usr/bin/env bash
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
if [ "$PWD" = "/" ]; then echo "Error: No WORKDIR set in Dockerfile." >&2; exit 1; fi
set +e
pytest /tests/test_outputs.py -v -rA --tb=short
code=$?
if [ "$code" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
