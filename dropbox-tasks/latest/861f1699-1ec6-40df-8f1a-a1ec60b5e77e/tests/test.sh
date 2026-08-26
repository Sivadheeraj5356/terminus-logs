#!/bin/bash

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    exit 1
fi

TEST_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /opt/verifier-fixtures
cp -a "${TEST_DIR}/verifier-fixtures/." /opt/verifier-fixtures/ 2>/dev/null || true
cd /app/environment && make >/dev/null 2>&1 || true
cd /app

pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
