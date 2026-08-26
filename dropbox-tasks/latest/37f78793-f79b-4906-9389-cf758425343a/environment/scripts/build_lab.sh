#!/usr/bin/env bash
set -euo pipefail
cd /app/environment
mkdir -p /app/output /app/var/lab /app/bin /app/environment/tools/mdl_lab
go build -o /app/bin/mdl_lab ./cmd/mdl_lab
ln -sfn /app/bin/mdl_lab /app/environment/tools/mdl_lab/mdl_lab
