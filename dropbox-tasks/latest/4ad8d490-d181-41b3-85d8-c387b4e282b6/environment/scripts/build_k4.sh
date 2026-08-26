#!/bin/bash
set -euo pipefail
cd /app/environment
if [[ -x ./node_modules/.bin/tsc ]]; then
  ./node_modules/.bin/tsc -p tsconfig.json
else
  npx --no-install tsc -p tsconfig.json
fi
