#!/bin/bash
set -euo pipefail
cp /solution/fixed_release.js /app/src/release.js
npm run check
