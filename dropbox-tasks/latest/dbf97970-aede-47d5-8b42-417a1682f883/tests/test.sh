#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    exit 1
fi
WORKDIR=/run/verifier
mkdir -p "$WORKDIR"
rm -f "$WORKDIR"/*.py 2>/dev/null || true
unset PYTHONPATH PYTHONSTARTUP
cd "$WORKDIR" || exit 1
python3 -I -m pytest -p no:cacheprovider --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
pytest_status=$?
test "$pytest_status" -eq 0 && python3 - <<'PYEOF'
import json, sys
with open("/logs/verifier/ctrf.json") as fh:
    s = json.load(fh)["results"]["summary"]
sys.exit(0 if s.get("tests", 0) > 0 and s.get("failed", 1) == 0 and s.get("passed", 0) == s.get("tests", 0) else 1)
PYEOF
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
