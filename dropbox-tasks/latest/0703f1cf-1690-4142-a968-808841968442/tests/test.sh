#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    echo 0 > /logs/verifier/reward.txt
    exit 0
fi

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The submitted tool is executed as an unprivileged user during these tests.
# Deny that user any access to this mounted verifier directory (the test
# module and its embedded ground truth) so it cannot read or import the
# expected answers. Scoped to TEST_DIR itself only.
chmod -R go-rwx "$TEST_DIR" 2>/dev/null || true

python -m pytest --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -rA -p no:cacheprovider
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
