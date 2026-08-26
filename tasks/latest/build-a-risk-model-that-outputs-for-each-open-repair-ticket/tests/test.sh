#!/bin/bash
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
printf '%s
' '{"results":{"tool":{"name":"pytest"},"summary":{"tests":1,"passed":0,"failed":1,"pending":0,"skipped":0,"other":0,"start":0,"stop":0},"tests":[{"name":"verifier_precondition","status":"failed","duration":0}]}}' > /logs/verifier/ctrf.json

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    printf '%s
' '{"results":{"tool":{"name":"pytest"},"summary":{"tests":1,"passed":0,"failed":1,"pending":0,"skipped":0,"other":0,"start":0,"stop":0},"tests":[{"name":"environment_precondition","status":"failed","duration":0}]}}' > /logs/verifier/ctrf.json
    exit 0
fi

PYTHONSAFEPATH=1 python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
