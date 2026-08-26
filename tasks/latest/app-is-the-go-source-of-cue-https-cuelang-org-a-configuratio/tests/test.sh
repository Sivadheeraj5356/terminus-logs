#!/bin/bash
# Verifier entrypoint. Runs the held-out CUE evaluation tests and writes the
# reward. NOTE: no `set -e` and no trailing `exit` — must END with the reward block.
mkdir -p /logs/verifier
if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set."
  exit 1
fi
python3 -m pytest -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
