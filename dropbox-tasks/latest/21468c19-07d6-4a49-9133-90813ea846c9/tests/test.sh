#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

TEST_DIR="${TEST_DIR:-/tests}"
VERIFY_PY="/opt/test-venv/bin/python3"
AGENT_UID=65534
AGENT_GID=65534

restore_permissions() {
    if [ -d "$TEST_DIR" ]; then
        chmod -R a+rX "$TEST_DIR" >/dev/null 2>&1 || true
    fi
    if [ -d /solution ]; then
        chmod -R a+rX /solution >/dev/null 2>&1 || true
    fi
    if [ -d /logs/verifier ]; then
        chmod -R u+rwX,go-rwx /logs/verifier >/dev/null 2>&1 || true
    fi
}

protect_tree() {
    if [ -e "$1" ]; then
        chmod -R u+rwX,go-rwx "$1"
    fi
}

assert_agent_cannot_read() {
    "$VERIFY_PY" - "$1" <<'PY'
import os
import pathlib
import sys

target = pathlib.Path(sys.argv[1])
try:
    os.setgid(65534)
    os.setuid(65534)
    if target.is_dir():
        next(target.iterdir())
    else:
        target.read_bytes()
except (FileNotFoundError, PermissionError):
    sys.exit(0)
except StopIteration:
    sys.exit(0)
sys.exit(1)
PY
}

run_analysis_as_agent() {
    "$VERIFY_PY" <<'PY'
import os
import subprocess
import sys

env = os.environ.copy()
env["HOME"] = "/tmp"
env["R_USER"] = "/tmp"
env["TMPDIR"] = "/tmp"
os.setgid(65534)
os.setuid(65534)
result = subprocess.run(
    ["Rscript", "/app/analysis.R"],
    cwd="/app",
    env=env,
    text=True,
    capture_output=True,
    timeout=1700,
)
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
PY
}

trap restore_permissions EXIT

if [ "$PWD" = "/" ]; then
    echo "Error: no working directory set."
    false
elif [ ! -f /app/analysis.R ]; then
    echo "Error: /app/analysis.R is missing."
    false
elif grep -E -i '(/tests|test_outputs[.]py|/solution|solution/|/logs/verifier|reward[.]txt|ctrf[.]json)' /app/analysis.R >/dev/null; then
    echo "Error: analysis.R references protected verifier, solution, or reward paths."
    false
else
    rm -rf /app/outputs
    mkdir -p /app/outputs
    chown -R "$AGENT_UID:$AGENT_GID" /app/outputs
    chmod 700 /app/outputs
    protect_tree "$TEST_DIR"
    protect_tree /solution
    protect_tree /logs/verifier
    if ! assert_agent_cannot_read "$TEST_DIR/test_outputs.py"; then
        echo "Error: verifier tests are readable by the submitted analysis user."
        false
    elif [ -f /logs/verifier/reward.txt ] && ! assert_agent_cannot_read /logs/verifier/reward.txt; then
        echo "Error: verifier reward output is readable by the submitted analysis user."
        false
    else
        reward_before="$(stat -c '%Y:%s' /logs/verifier/reward.txt)"
        run_analysis_as_agent
        analysis_status=$?
        reward_after="$(stat -c '%Y:%s' /logs/verifier/reward.txt)"
        if [ "$analysis_status" -ne 0 ]; then
            false
        elif [ "$reward_before" != "$reward_after" ]; then
            echo "Error: analysis.R modified verifier reward output."
            false
        else
            restore_permissions
            "$VERIFY_PY" -m pytest -rA "$TEST_DIR/test_outputs.py" --ctrf /logs/verifier/ctrf.json -o cache_dir=/tmp/pytest_cache
        fi
    fi
fi
test_status=$?
if [ "$test_status" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
