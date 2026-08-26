#!/usr/bin/env bash
set -euo pipefail

cd /app
go build -o /app/bin/cl_publish ./cmd/ovpub
exec /app/bin/cl_publish
