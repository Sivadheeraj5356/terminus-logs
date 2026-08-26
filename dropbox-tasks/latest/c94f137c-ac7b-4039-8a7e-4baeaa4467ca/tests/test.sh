#!/bin/bash

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
printf '%s\n' '{"version":"1.0.0","results":{"tool":{"name":"pytest"}},"summary":{"tests":0,"passed":0,"failed":0,"pending":0,"skipped":0,"other":0},"tests":[]}' > /logs/verifier/ctrf.json

cd /app
cd /app/environment && go build -o /app/bin/claimdocketaudit ./cmd/claimdocketaudit
cd /app

UV_OFFLINE=1 uvx \
  -p 3.13 \
  -w pytest==8.4.1 \
  -w pytest-json-ctrf==0.3.5 \
  -w crc32c==2.7.1 \
  pytest \
    -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json \
    /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
