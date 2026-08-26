#!/bin/bash
set -uo pipefail

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    mkdir -p /logs/verifier
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

mkdir -p /logs/verifier

export PATH="/usr/local/go/bin:/go/bin:${PATH}"
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_CACHE_DIR="${PYTEST_CACHE_DIR:-/tmp/pytest_cache}"
mkdir -p "$PYTEST_CACHE_DIR" /app/bin /app/output

set +e
python3 -m pytest -o "cache_dir=${PYTEST_CACHE_DIR}" \
    --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
