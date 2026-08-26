#!/bin/bash
set -euo pipefail
cd /app
cp /solution/main.ts /app/src/main.ts
make
