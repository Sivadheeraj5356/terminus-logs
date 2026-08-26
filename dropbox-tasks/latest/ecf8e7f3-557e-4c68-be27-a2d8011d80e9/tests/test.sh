#!/bin/bash
set -uo pipefail

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set."
  exit 1
fi

mkdir -p /logs/verifier
export PYTHONDONTWRITEBYTECODE=1

/opt/venv/bin/python -m pytest --ctrf /logs/verifier/ctrf.json \
  -o cache_dir=/tmp/pnpmfix-pytest-cache /tests/test_outputs.py -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
