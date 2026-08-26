#!/bin/bash

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    exit 1
fi

mkdir -p /logs/verifier

python3 -m pytest /tests/test_outputs.py -rA
code=$?

if [ "$code" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
