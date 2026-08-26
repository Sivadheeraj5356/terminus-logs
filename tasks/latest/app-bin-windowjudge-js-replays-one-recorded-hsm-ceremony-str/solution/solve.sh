#!/bin/bash
set -euo pipefail
cd /app
if patch -p1 --dry-run --forward < /solution/fix.patch >/dev/null 2>&1; then
    patch -p1 --forward < /solution/fix.patch
fi
node --check bin/windowjudge.js
node --check lib/judge.js
