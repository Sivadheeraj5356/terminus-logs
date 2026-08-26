#!/bin/bash
set -euo pipefail
export PATH="/usr/local/go/bin:/usr/local/bin:${PATH}"
cd /app/environment
go build -o /app/bin/linkctl ./cmd/linkctl
