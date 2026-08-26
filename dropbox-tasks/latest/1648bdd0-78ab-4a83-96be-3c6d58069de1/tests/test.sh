#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set." >&2
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

# Intentionally omit -e so pytest failures still reach the reward write.
python -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
