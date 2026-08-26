#!/bin/bash
set -euo pipefail
cd /app
exec cargo build --offline --locked "$@"
