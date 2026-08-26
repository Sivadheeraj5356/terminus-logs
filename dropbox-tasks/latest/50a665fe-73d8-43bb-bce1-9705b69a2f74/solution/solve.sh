#!/bin/bash
set -euo pipefail

cp /solution/main.go /app/task_file/main.go
cd /app/task_file
gofmt -w main.go
go build -trimpath -o conclave .
mkdir -p output
./conclave input/public_match.json output/adjudication.json

