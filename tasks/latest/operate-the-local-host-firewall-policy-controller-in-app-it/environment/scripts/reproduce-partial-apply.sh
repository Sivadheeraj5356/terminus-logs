#!/usr/bin/env bash
set -euo pipefail
cd /app
/app/bin/nxctl reset-demo
NX_FAILPOINT=after-stage-sets /app/bin/nxctl apply || true
/app/bin/nxctl status --json
/app/bin/nxctl inspect --json
/app/bin/nxctl recover --json
