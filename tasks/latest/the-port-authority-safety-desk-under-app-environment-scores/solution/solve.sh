#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

bash steps/write_q4n.sh
bash steps/write_j8r.sh
bash steps/write_v2x.sh
cd /app/environment
npm run build >/dev/null
/app/environment/tools/k9ctl score
