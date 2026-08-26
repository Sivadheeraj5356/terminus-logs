#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set." >&2
  echo 0 > /logs/verifier/reward.txt
  exit 1
fi

export TEST_DIR="${TEST_DIR:-/tests}"

if [ ! -f /app/.tbench-testing/bin/activate ]; then
  echo "Error: prebuilt verifier venv missing at /app/.tbench-testing" >&2
  echo 0 > /logs/verifier/reward.txt
  exit 1
fi

# shellcheck disable=SC1091
source /app/.tbench-testing/bin/activate

if ! redis-cli ping >/dev/null 2>&1; then
  redis-server --daemonize yes --port 6379 --bind 127.0.0.1 --save "" --appendonly no
  sleep 1
fi

set +e
pytest -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_m3.py" -rA
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
