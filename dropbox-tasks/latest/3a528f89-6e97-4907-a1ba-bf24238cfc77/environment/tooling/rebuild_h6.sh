#!/bin/bash
set -euo pipefail
export PATH="/usr/local/go/bin:${PATH}"
cd /app/environment
go build -o /app/environment/tools/cmd_h6 ./cmd_h6
