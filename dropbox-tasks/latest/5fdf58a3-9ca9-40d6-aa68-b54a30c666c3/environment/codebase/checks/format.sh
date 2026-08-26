#!/usr/bin/env bash
set -euo pipefail

node --check /app/src/worker.js

echo "format ok"
