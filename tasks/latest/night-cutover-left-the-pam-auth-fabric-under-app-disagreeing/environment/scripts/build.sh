#!/bin/bash
set -euo pipefail
cd /app
make clean >/dev/null 2>&1 || true
make all
test -x /app/bin/pam_audit
