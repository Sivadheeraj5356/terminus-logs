#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: WORKDIR not configured"
  exit 1
fi

# Remove any agent-accessible copy of hidden data before running tests
rm -f /app/input/collections_hidden.json /app/collections_hidden.json

# Restrict hidden fixture from candidate binary reads
chmod 600 /tests/collections_hidden.json 2>/dev/null || true

python3 -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
