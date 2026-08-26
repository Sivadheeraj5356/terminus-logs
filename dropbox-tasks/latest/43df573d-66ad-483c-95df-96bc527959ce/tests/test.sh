#!/bin/bash
mkdir -p /logs/verifier
CTRF=/logs/verifier/ctrf.json
printf '%s' '{"results":{"tool":{"name":"pytest"},"summary":{"tests":1,"passed":0,"failed":1,"pending":0,"skipped":0,"other":0},"tests":[{"name":"setup","status":"failed","duration":0}]}}' > "$CTRF"
if [ "$PWD" = "/" ]; then
  echo "no working directory set" >&2
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi
cd /app
python3 -m pytest -rA -p no:cacheprovider --ctrf "$CTRF" /tests/test_outputs.py
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
