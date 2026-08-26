#!/bin/bash
set -euo pipefail
ENV_FILE="${1:-/app/environment/fixtures/site_j4.env}"
SITE="$(grep '^SITE=' "${ENV_FILE}" | cut -d= -f2)"
CODE="$(/app/environment/q3_probe/admit_run --site "${SITE}" --mode work)"
echo "${CODE}" > "/app/work/policy/probe_${SITE}_work.txt"
