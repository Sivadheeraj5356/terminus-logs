#!/bin/bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
  echo "no working directory" >&2
  exit 1
fi

cd "$(dirname "$0")"

python3 -m pytest -p no:cacheprovider -rA --ctrf /logs/verifier/ctrf.json test_outputs.py
PYTEST_EXIT=$?
(exit $PYTEST_EXIT)
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
