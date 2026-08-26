#!/bin/bash
mkdir -p /logs/verifier

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

rm -rf /app/outputs
mkdir -p /app/outputs
timeout 600 /app/run_analysis_guarded.sh
r_rc=$?
python3 -m pytest -p no:cacheprovider --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -v -rA
pytest_rc=$?

if [ "$r_rc" -eq 0 ] && [ "$pytest_rc" -eq 0 ]; then
    true
else
    false
fi
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
