#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
TEST_DIR="${TEST_DIR:-/tests}"

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi

# Keep grading artifacts out of reach of the submitted Ruby/Go child processes.
# Re-exec from a private copy FIRST, then redact the Harbor-mounted /tests tree.
# (Redacting /tests/test.sh while bash is still reading it truncates the script
#  before the reward block and causes RewardFileNotFoundError.)
if [ "${VERIFIER_ISOLATED:-}" != "1" ]; then
    PRIV_DIR="/tmp/verifier-$$"
    cp -a "$TEST_DIR" "$PRIV_DIR"
    export VERIFIER_ISOLATED=1
    export TEST_DIR="$PRIV_DIR"
    exec bash "$PRIV_DIR/test.sh"
fi

if [ -d /tests ]; then
    find /tests -type f \( -name '*.py' -o -name '*.rb' -o -name '*.sh' \) -print0 \
      | while IFS= read -r -d '' f; do
            printf '# relocated\n' > "$f"
        done
fi

/opt/verifier-venv/bin/python -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json "$TEST_DIR/test_outputs.py" -rA
if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
