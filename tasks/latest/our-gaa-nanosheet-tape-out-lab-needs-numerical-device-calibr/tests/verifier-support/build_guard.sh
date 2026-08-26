#!/bin/bash
# Rebuild the submitted tb3 kernel from the agent's current source under the
# strace trace guard, so that no Cargo build script can open the mounted
# reference tests in /tests or the oracle tree in /solution. Effective command:
#   cargo build --release --locked -p tb3
# The build is launched through trace_run.py, which rejects any open() that
# resolves into those protected roots (or /proc/self/root aliases).
set -u

TEST_DIR="${TEST_DIR:-/tests}"
cd /app || exit 1

# Force a clean rebuild from the agent's source rather than any prebuilt binary.
cargo clean -p tb3 >/dev/null 2>&1 || true

exec /opt/verifier-venv/bin/python3 "${TEST_DIR}/verifier-support/trace_run.py" \
  --policy tests --cwd /app -- \
  cargo build --release --locked -p tb3

