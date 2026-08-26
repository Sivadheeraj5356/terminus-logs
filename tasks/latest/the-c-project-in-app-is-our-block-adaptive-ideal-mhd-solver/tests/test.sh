#!/bin/bash
# Verifier dependencies (pytest, pytest-json-ctrf, numpy) are baked into environment/Dockerfile;
# nothing is installed here.
set -uo pipefail

mkdir -p /logs/verifier

# Fail loudly rather than silently scoring zero if the image has no WORKDIR set.
if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Set a WORKDIR in the Dockerfile."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

# Produce reward file (REQUIRED)
python3 -m pytest -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
