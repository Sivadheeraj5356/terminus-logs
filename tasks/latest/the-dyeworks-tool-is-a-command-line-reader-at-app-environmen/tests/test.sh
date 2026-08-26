#!/usr/bin/env bash

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  cd /app/environment || true
fi

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

if [ -d /opt/verifier-venv/bin ]; then
  export PATH="/opt/verifier-venv/bin:${PATH}"
fi

python3 -m pytest -rA --ctrf /logs/verifier/ctrf.json -p no:cacheprovider -o addopts="" "${TEST_DIR}/test_outputs.py"
status=$?

if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
