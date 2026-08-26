#!/usr/bin/env bash
set -euo pipefail
/app/bin/nxctl reset-demo --state-dir "${NX_STATE_DIR:-/app/state}"
