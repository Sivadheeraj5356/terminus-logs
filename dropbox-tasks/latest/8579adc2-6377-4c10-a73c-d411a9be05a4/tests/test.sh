#!/bin/bash
mkdir -p /logs/verifier

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

/opt/verifier-venv/bin/python -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -v -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
