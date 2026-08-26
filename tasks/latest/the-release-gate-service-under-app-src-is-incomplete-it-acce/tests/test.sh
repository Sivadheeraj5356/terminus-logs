#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No WORKDIR set. Add WORKDIR to your Dockerfile." >&2
    exit 1
fi

# Start the gate service (solve.sh leaves it stopped after smoke-check).
bash /app/scripts/run_gate.sh

/opt/verifier-venv/bin/pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
