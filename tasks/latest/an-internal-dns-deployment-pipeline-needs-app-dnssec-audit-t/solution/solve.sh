#!/bin/bash
set -euo pipefail

cd /app
patch -p1 < /solution/fix.patch
gofmt -w audit/audit.go
go build -o /app/dnssec-audit ./cmd/dnssec-audit
