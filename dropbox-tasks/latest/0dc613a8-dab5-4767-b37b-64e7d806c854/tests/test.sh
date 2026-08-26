#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set." ; echo 0 > /logs/verifier/reward.txt ; exit 0
fi
python3 -m pytest --ctrf /logs/verifier/ctrf.json -p no:cacheprovider /tests/test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then echo 1 > /logs/verifier/reward.txt; else echo 0 > /logs/verifier/reward.txt; fi
