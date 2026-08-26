#!/usr/bin/env bash
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
TEST_DIR="${TEST_DIR:-/tests}"
if [ ! -f "$TEST_DIR/test_m2.py" ]; then
  TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

python3 -m pytest -rA -o cache_dir=/tmp/pytest_cache "$TEST_DIR/test_m2.py"
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
