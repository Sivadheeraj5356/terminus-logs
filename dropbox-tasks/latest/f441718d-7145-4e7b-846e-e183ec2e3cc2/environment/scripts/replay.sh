#!/usr/bin/env bash
# Deterministic replay driver — rebuilds replay artifacts from persisted journal.
set -euo pipefail

export PATH="/usr/local/go/bin:/usr/local/bin:/tmp:${PATH:-}"
ROOT="${RUNTIME_ROOT:-${TB3_APP_ROOT:-/app}}"
BIN="${RUNTIME_BIN:-/tmp/runtime}"
export RUNTIME_ROOT="${ROOT}"
cd "${ROOT}"

if [[ ! -x "${BIN}" ]]; then
  go build -o "${BIN}" ./cmd/runtime
fi

"${BIN}" replay
echo "replay: wrote state/replay.json"
