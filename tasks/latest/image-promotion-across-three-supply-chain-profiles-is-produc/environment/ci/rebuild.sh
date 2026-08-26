#!/bin/bash
set -euo pipefail
cd /app/environment
go build -o /app/bin/pull_gate ./q9/pull_gate
go build -o /app/bin/sync_probe ./cmd/probe_stage
go build -o /app/bin/meta_walk ./cmd/meta_walk
go build -o /app/bin/collect_stage ./cmd/collect_stage
