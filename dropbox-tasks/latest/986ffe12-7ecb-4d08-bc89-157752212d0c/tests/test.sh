#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Set WORKDIR in Dockerfile."
    exit 0
fi

export PATH="/usr/local/go/bin:/go/bin:${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"

cd /app
go build -o /app/bin/gachaudit ./cmd/gachaudit 2>&1
BUILD_RC=$?
if [ $BUILD_RC -ne 0 ]; then
    echo "Build failed with exit code $BUILD_RC"
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

mkdir -p /app/output
rm -f /app/output/pity_ledger.json
/app/bin/gachaudit \
  --input /app/data/sessions.json \
  --config /app/config/gacha.json \
  --override /app/config/live_overrides.toml \
  --ledger /app/output/pity_ledger.json \
  --output /app/output/report.json 2>&1

python3 -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -v -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
