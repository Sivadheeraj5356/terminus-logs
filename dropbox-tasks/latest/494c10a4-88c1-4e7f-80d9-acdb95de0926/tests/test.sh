#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
rm -f /app/analyze
cd /app && make
cd /tests || exit 1
python3 -m pytest -rA -p no:cacheprovider --confcutdir=/tests -c /tests/pytest.ini --ctrf /logs/verifier/ctrf.json test_outputs.py
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
