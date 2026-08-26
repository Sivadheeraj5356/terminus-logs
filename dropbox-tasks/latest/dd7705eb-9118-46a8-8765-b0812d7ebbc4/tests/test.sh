#!/bin/bash

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

python3 -m pytest -o cache_dir=/tmp/pytest_cache --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -v -rA --tb=short

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
