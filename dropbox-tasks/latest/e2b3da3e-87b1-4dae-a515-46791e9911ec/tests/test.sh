#!/bin/bash
set -uo pipefail

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    mkdir -p /logs/verifier
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

mkdir -p /logs/verifier

# Keep verifier sources readable by root pytest, but not by the unprivileged candidate.
chown -R root:root /tests
chmod -R u=rwX,g=,o= /tests

# Strip setuid/setgid bits under /app before candidate execution.
find /app -xdev \( -perm -4000 -o -perm -2000 \) -type f -exec chmod a-s {} + 2>/dev/null || true

# Run pytest from a fresh root-owned directory outside /app.
VERIFIER_CWD="$(mktemp -d /tmp/lockctl-pytest-XXXXXX)"
chmod 0700 "$VERIFIER_CWD"
cd "$VERIFIER_CWD" || exit 0

python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
