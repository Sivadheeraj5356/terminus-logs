#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "${ROOT_DIR}/patched/accum/interval.go" /app/environment/accum/interval.go
cp "${ROOT_DIR}/patched/accum/merge.go" /app/environment/accum/merge.go
cp "${ROOT_DIR}/patched/accum/window.go" /app/environment/accum/window.go
cp "${ROOT_DIR}/patched/audit/audit.go" /app/environment/audit/audit.go
cp "${ROOT_DIR}/patched/cmd/orchardledger/main.go" /app/environment/cmd/orchardledger/main.go
cp "${ROOT_DIR}/patched/config/settings.go" /app/environment/config/settings.go
cp "${ROOT_DIR}/patched/config/toml_decode.go" /app/environment/config/toml_decode.go
cp "${ROOT_DIR}/patched/corrections/corrections.go" /app/environment/corrections/corrections.go
cp "${ROOT_DIR}/patched/emit/write.go" /app/environment/emit/write.go
cp "${ROOT_DIR}/patched/manifest/manifest.go" /app/environment/manifest/manifest.go
cp "${ROOT_DIR}/patched/parse/readings.go" /app/environment/parse/readings.go
cp "${ROOT_DIR}/patched/registry/registry.go" /app/environment/registry/registry.go
cp "${ROOT_DIR}/patched/replay/replay.go" /app/environment/replay/replay.go
cp "${ROOT_DIR}/patched/state/hash.go" /app/environment/state/hash.go
cp "${ROOT_DIR}/patched/state/state.go" /app/environment/state/state.go
cp "${ROOT_DIR}/patched/util/util.go" /app/environment/util/util.go

grep -q replayWindowStart /app/environment/replay/replay.go

cd /app/environment
go build -o /tmp/orchard-ledger ./cmd/orchardledger
mkdir -p /app/output

/tmp/orchard-ledger replay \
  --manifest /app/environment/fixtures/replay_manifest.toml \
  --out /app/output \
  --state /app/output/replay_state.json
