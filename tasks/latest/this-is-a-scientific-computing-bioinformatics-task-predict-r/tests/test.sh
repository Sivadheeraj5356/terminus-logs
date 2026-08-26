#!/usr/bin/env bash
set -uo pipefail

mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set." >&2
    exit 1
fi

export APP_DIR="${APP_DIR:-/app}"
cd "$(dirname "$0")"

VENV_PY="${VERIFIER_VENV:-/opt/verifier-venv}/bin/python"
"$VENV_PY" -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
status=$?
if [ "$status" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
