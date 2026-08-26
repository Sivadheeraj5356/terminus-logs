#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app

# Swap in the finished implementations of the four packages the pipeline needs.
cp "$SCRIPT_DIR/snippets/cidr.go"    /app/internal/cidr/cidr.go
cp "$SCRIPT_DIR/snippets/ruleset.go" /app/internal/ruleset/ruleset.go
cp "$SCRIPT_DIR/snippets/eval.go"    /app/internal/eval/eval.go
cp "$SCRIPT_DIR/snippets/report.go"  /app/internal/report/report.go

# Confirm the real implementations landed before building.
grep -q '32 - prefix' /app/internal/cidr/cidr.go
grep -q 'srcNet.Canonical()' /app/internal/ruleset/ruleset.go
grep -q 'func ordered(' /app/internal/eval/eval.go
grep -q 'flagged++' /app/internal/report/report.go

go build -o bin/acl ./cmd/acl
go test ./... >/dev/null

# Smoke run of both subcommands.
./bin/acl evaluate --rules testdata/rules_main.json --flows testdata/flows_main.ndjson >/dev/null
./bin/acl lint --rules testdata/rules_main.json --flows testdata/flows_main.ndjson >/dev/null
