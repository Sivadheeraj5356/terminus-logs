#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

# The verifier stays root so it can import its oracle, but the submitted source
# is compiled and executed as the dedicated arcguard user. Hide all protected
# grading material, plus solution material when the runner mounted it, before
# pytest starts. Evaluation runners are not required to provide /solution.
protected_paths=(/tests)
if [ -e /solution ]; then
    protected_paths+=(/solution)
fi
if ! chmod -R go-rwx "${protected_paths[@]}"; then
    echo "Error: Could not protect verifier and solution paths."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

"${VERIFIER_PYTHON:-/opt/verifier-venv/bin/python}" -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
rc=$?

if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
