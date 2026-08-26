#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set."
  exit 0
fi

rm -f /tmp/arcplan-verifier
if ! /usr/local/go/bin/go build -trimpath -o /tmp/arcplan-verifier /app/src/main.go; then
  exit 0
fi

ARCPLAN_BINARY=/tmp/arcplan-verifier python -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
