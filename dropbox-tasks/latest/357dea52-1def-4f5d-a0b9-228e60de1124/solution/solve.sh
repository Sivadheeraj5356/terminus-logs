#!/bin/bash
set -euo pipefail

mkdir -p /workspace/cmd/breakglass-ledger /workspace/bin /workspace/output
cp /solution/main.go /workspace/cmd/breakglass-ledger/main.go
cd /workspace/cmd/breakglass-ledger
GO111MODULE=off go build -o /workspace/bin/breakglass-ledger .
/workspace/bin/breakglass-ledger /workspace/task_file/breakglass_ledger_case.json /workspace/output/breakglass_ledger_report.json
