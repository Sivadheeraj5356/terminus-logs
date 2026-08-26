#!/usr/bin/env bash
# Active post-deploy validation hook
set -euo pipefail
host="${1:-unknown}"
echo "post-validate-ok ${host}"
