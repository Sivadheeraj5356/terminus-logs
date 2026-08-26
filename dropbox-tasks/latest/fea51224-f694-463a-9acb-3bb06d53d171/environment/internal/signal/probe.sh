#!/bin/bash
set -euo pipefail
ROOT="${REPLAY_ROOT:-/app/environment}"
mkdir -p /tmp/probe-out
/app/bin/volutil run /tmp/probe-out >/dev/null 2>&1 || true
exit 0
