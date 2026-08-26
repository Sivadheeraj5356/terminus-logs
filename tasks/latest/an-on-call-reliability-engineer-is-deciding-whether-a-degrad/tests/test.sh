#!/usr/bin/env bash
set -euo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
export PYTHONPATH="/tests/wheels/pytest-8.4.1-py3-none-any.whl:/tests/wheels/pluggy-1.6.0-py3-none-any.whl:/tests/wheels/packaging-25.0-py3-none-any.whl:/tests/wheels/iniconfig-2.1.0-py3-none-any.whl:/tests/wheels/pygments-2.19.2-py3-none-any.whl"

set +e
timeout 100s python3 -m pytest /tests/test_outputs.py -q -rA -p no:cacheprovider
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
