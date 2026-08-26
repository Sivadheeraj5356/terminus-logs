#!/bin/bash
set -euo pipefail
export TB_POND_FIXTURE=1
exec /app/bin/pond_ctl
