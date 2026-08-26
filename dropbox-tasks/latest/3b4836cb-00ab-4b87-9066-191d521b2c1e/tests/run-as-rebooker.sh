#!/bin/bash
set -euo pipefail
RUNUSER_BIN="/opt/verifier-bin/runuser"
if [ ! -x "${RUNUSER_BIN}" ]; then
    echo "trusted runuser missing" >&2
    exit 1
fi
exec "${RUNUSER_BIN}" "$@"
