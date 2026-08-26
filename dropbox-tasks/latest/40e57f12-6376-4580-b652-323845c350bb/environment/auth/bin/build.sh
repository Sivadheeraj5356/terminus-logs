#!/bin/bash
set -euo pipefail
cd /app/auth
CGO_ENABLED=1 go build -o /app/auth/bin/tokensvc /app/auth/cmd/tokensvc
