#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set." >&2
    exit 1
fi

# Run the verifier from /tests (never the agent-writable /app) with a safe import path, plugin
# autoload off, conftest discovery off, and a pinned config, so nothing the agent dropped under
# /app can shadow a stdlib module, inject pytest options, or otherwise short-circuit grading.
cd /tests || { echo "verifier dir missing" >&2; exit 1; }
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
/opt/verifier-venv/bin/python -P -m pytest \
    test_outputs.py -rA \
    -p no:cacheprovider -p ctrf.main \
    --noconftest --import-mode=importlib \
    -c /tests/pytest.ini -o addopts= \
    --ctrf /logs/verifier/ctrf.json
RC=$?
if [ "$RC" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
