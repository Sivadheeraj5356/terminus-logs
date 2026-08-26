#!/bin/bash
mkdir -p /logs/verifier

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    mkdir -p /tmp/verifier-preflight-failed
    printf '%s\n' \
        'def test_workdir_is_configured():' \
        '    assert False, "No working directory set."' \
        > /tmp/verifier-preflight-failed/test_preflight_failed.py
    /opt/verifier-venv/bin/python -m pytest -p no:cacheprovider --ctrf /logs/verifier/ctrf.json /tmp/verifier-preflight-failed -v -rA
else
    cd /app/environment
    /opt/verifier-venv/bin/python -m pytest -p no:cacheprovider --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -v -rA
fi
pytest_status=$?
if [ "$pytest_status" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
