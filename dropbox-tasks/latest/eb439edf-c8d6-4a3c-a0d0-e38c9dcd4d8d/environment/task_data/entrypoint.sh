#!/usr/bin/env bash
set -euo pipefail

# Copy task data files into /workspace for the agent.
# -n (no-clobber): do not overwrite files the oracle/agent has already written.
cp -n /opt/task_data/codex.txt    /workspace/codex.txt    2>/dev/null || true
cp -n /opt/task_data/sessions.json /workspace/sessions.json 2>/dev/null || true

exec "$@"
