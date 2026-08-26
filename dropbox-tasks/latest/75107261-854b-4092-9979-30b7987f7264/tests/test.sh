#!/bin/bash
# Offline verifier entrypoint: run the unitgraph docket and emit Harbor reward + CTRF.
# Installs nothing and uses no network; pytest lives in /opt/unitgraph_verifier_venv.
mkdir -p /logs/verifier

/opt/unitgraph_verifier_venv/bin/python3 -m pytest -rA /tests/test_outputs.py -p no:cacheprovider --ctrf /logs/verifier/ctrf.json
status=$?
if [ "$status" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
