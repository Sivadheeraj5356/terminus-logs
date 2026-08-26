#!/usr/bin/env bash
set -euo pipefail
cd /app
cp "/solution/work/journal/resolve.go" "/app/internal/journal/resolve.go"
cp "/solution/work/authority/timeline.go" "/app/internal/authority/timeline.go"
cp "/solution/work/recovery/select.go" "/app/internal/recovery/select.go"
cp "/solution/work/envelope/aad.go" "/app/internal/envelope/aad.go"
cp "/solution/work/snapshot/snapshot.go" "/app/internal/snapshot/snapshot.go"
cp "/solution/work/checkpoint/checkpoint.go" "/app/internal/checkpoint/checkpoint.go"
cp "/solution/work/publish/publish.go" "/app/internal/publish/publish.go"
cp "/solution/work/inspect/inspect.go" "/app/internal/inspect/inspect.go"
make clean install
/app/bin/vault-qualify --vault /app/vault --output /tmp/oracle-smoke
test -f /tmp/oracle-smoke/inventory.jsonl
