#!/bin/bash
set -u
cd "$(dirname "$0")"
mkdir -p /logs/verifier
python3 -m pytest -p no:cacheprovider -rA -q test_outputs.py
RC=$?
if [ "$RC" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
