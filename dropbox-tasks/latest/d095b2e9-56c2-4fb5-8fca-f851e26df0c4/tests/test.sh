#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
TEST_DIR="${TEST_DIR:-/tests}"
cp "$TEST_DIR/ctrf_placeholder.json" /logs/verifier/ctrf.json
export PYTHONDONTWRITEBYTECODE=1

check_working_directory() {
  if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set." >&2
    return 1
  fi
  return 0
}

guard_status=0
check_working_directory || guard_status=$?
cd "$TEST_DIR" || guard_status=$?
python3 -I -m pytest -p no:cacheprovider -rA --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py"
pytest_status=$?
[ "$guard_status" -eq 0 ] && [ "$pytest_status" -eq 0 ]
status=$?
if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
