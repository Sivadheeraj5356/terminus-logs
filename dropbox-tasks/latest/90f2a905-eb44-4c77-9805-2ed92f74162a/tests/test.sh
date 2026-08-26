#!/bin/bash

mkdir -p /logs/verifier

write_failure_report() {
    printf '%s\n' '{"results":{"tool":{"name":"pytest"},"summary":{"tests":1,"passed":0,"failed":1,"pending":0,"skipped":0,"other":0,"start":0,"stop":0},"tests":[{"name":"verifier_bootstrap","status":"failed","duration":0,"message":"No working directory set"}]}}' > /logs/verifier/ctrf.json
}

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    write_failure_report
    false
else
    export PATH="/opt/venv/bin:/usr/local/go/bin:/usr/local/cargo/bin:${PATH}"
    export TASK_ENV="/app/environment"
    export TASK_TESTS="$(cd "$(dirname "$0")" && pwd)"
    export PYTHONDONTWRITEBYTECODE=1
    /opt/venv/bin/python3 -m pytest --ctrf /logs/verifier/ctrf.json -rA -p no:cacheprovider -o addopts="" "$TASK_TESTS/test_outputs.py"
fi
rc=$?

if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
