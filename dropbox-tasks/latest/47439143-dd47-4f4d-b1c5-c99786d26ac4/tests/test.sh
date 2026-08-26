#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

# The held-out corpus and the reference stay unreadable to submitted code, which
# the verifier runs as the unprivileged `sandbox` user.
chmod -R go-rwx /tests

/opt/verifier-venv/bin/python -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -v -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
