#!/bin/bash
set -u

mkdir -p /logs/verifier
TEST_DIR="${TEST_DIR:-/tests}"
CASE_ROOT="$(mktemp -d /tmp/mgus-cases.XXXXXX)"
export CASE_ROOT
export TEST_FIXTURES="$TEST_DIR/fixtures"

python3 "$TEST_DIR/generate_hidden_data.py" \
    --fixtures-dir "$TEST_FIXTURES" \
    --case-root "$CASE_ROOT"
generator_rc=$?
setup_rc="$generator_rc"

chown -R 65534:65534 "$CASE_ROOT" 2>/dev/null || setup_rc=1
chmod -R u+rwX,go-rwx "$TEST_DIR" || setup_rc=1
export FIXTURE_GENERATION_RC="$setup_rc"
cd "$TEST_DIR"

export PYTHONPATH=""
export PYTHONSAFEPATH=1
python3 -m pytest \
    -p no:cacheprovider \
    --ctrf /logs/verifier/ctrf.json \
    test_outputs.py \
    -rA
rc=$?
if [ "$rc" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
