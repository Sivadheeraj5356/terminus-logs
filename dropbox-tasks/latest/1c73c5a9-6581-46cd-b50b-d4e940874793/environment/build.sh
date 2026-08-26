#!/bin/bash
set -euo pipefail
cd /app
go build -trimpath -o /app/arcplan /app/src/main.go
