#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set."
  exit 1
fi
cd /app
python3 -m pytest -rA /tests/test_outputs.py --ctrf /logs/verifier/ctrf.json
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
