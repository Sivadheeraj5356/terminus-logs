#!/bin/bash
set -uo pipefail

# Verifier dependencies are installed in environment/Dockerfile.
# Add task-specific verifier-only Python packages there, not here.

ensure_files() {
  mkdir -p /logs/verifier
  # Always emit reward/ctrf so the harness never reports verifier_did_not_run
  # / "Failed to run difficulty check" when prep or pytest aborts early.
  if [ ! -f /logs/verifier/reward.txt ]; then
    echo 0 > /logs/verifier/reward.txt
  fi
  if [ ! -s /logs/verifier/ctrf.json ]; then
    cat > /logs/verifier/ctrf.json <<'EOF'
{"results":{"tool":{"name":"pytest"},"summary":{"tests":0,"passed":0,"failed":0,"pending":0,"skipped":0,"other":0,"start":0.0,"stop":0.0},"tests":[]},"version":"0.0.0"}
EOF
  fi
}

trap ensure_files EXIT

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

# Check if we're in a valid working directory
if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi

export RELOC_VERIFIER_ARTIFACT_DIR="${RELOC_VERIFIER_ARTIFACT_DIR:-/tmp/reloc-verifier-artifacts}"
export PYTHONDONTWRITEBYTECODE=1
# Block cwd-shadowed /app/pytest.py from hijacking "python3 -m pytest".
export PYTHONSAFEPATH=1

TEST_DIR="${TEST_DIR:-/tests}"

# Capture reports before pytest (avoids NOP/partial agents aborting the verifier
# under set -e via prepare_verifier_artifacts → verifier_did_not_run /
# Failed to run difficulty check).
# Run prep from /tests with safe path so /app modules cannot shadow imports.
cd "${TEST_DIR}"
PYTHONPATH="${TEST_DIR}" python3 -P <<'PY' || true
import os
import sys

sys.path.insert(0, os.environ.get("TEST_DIR", "/tests"))
try:
    from test_outputs import prepare_verifier_artifacts

    prepare_verifier_artifacts()
except Exception as exc:  # noqa: BLE001 - best-effort prep for NOP/partial agents
    print(f"prepare_verifier_artifacts skipped: {exc}", file=sys.stderr)
PY

# Prefer the absolute console-script entrypoint; fall back to python3 -P -m pytest.
# Always invoke from /tests so a planted /app/pytest.py cannot win.
cd "${TEST_DIR}"
export PYTHONPATH="${TEST_DIR}"

if [ -x /usr/local/bin/pytest ]; then
  /usr/local/bin/pytest -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py" -rA
elif command -v pytest >/dev/null 2>&1; then
  pytest -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py" -rA
else
  python3 -P -m pytest -o cache_dir=/tmp/pytest_cache \
    --ctrf /logs/verifier/ctrf.json "${TEST_DIR}/test_outputs.py" -rA
fi
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
