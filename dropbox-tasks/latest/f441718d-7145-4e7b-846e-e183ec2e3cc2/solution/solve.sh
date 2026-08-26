#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/go/bin:/usr/local/bin:/tmp:${PATH:-}"

ROOT="${RUNTIME_ROOT:-/app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES="${SCRIPT_DIR}/files"
cd "${ROOT}"

for file in \
  internal/hash/hash.go \
  internal/graph/graph.go \
  internal/policy/policy.go \
  internal/cache/cache.go \
  internal/journal/journal.go \
  internal/state/state.go \
  internal/util/canonical.go \
  internal/parser/parser.go \
  internal/compiler/compiler.go \
  internal/scheduler/scheduler.go \
  internal/executor/executor.go \
  internal/checkpoint/checkpoint.go \
  internal/recovery/recovery.go \
  internal/replay/replay.go \
  internal/verification/verification.go \
  internal/certificate/certificate.go \
  scripts/run_pipeline.sh \
  cmd/runtime/main.go; do
  if [[ -f "${FILES}/${file}" ]]; then
    mkdir -p "$(dirname "${ROOT}/${file}")"
    cp -f "${FILES}/${file}" "${ROOT}/${file}"
  fi
done

chmod +x "${ROOT}/scripts/"*.sh
go build -o /tmp/runtime ./cmd/runtime
test -x /tmp/runtime
if [[ -w /usr/local/bin ]]; then
  cp -f /tmp/runtime /usr/local/bin/runtime
fi
echo "solve: applied reference repairs and rebuilt runtime"
