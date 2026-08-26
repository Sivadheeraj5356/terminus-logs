#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
trap 'if [ ! -f /logs/verifier/reward.txt ]; then echo 0 > /logs/verifier/reward.txt; fi' EXIT

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

set +e
/opt/verifier-venv/bin/python -m pytest \
    --ctrf /logs/verifier/ctrf.json \
    -p no:cacheprovider \
    -rA /tests/test_outputs.py
status=$?
if [ "$status" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
