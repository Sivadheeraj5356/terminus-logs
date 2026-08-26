#!/bin/bash
set -euo pipefail

cp /solution/main.go /app/main.go
cd /app
go build -trimpath -ldflags='-s -w' -o /app/adjudicate /app/main.go
PATH=/no-helper-programs /app/adjudicate
test -s /app/output/result.json
