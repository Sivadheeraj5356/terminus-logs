#!/usr/bin/env bash
# Recovery driver — resumes from latest checkpoint.
set -euo pipefail

export PATH="/usr/local/go/bin:/usr/local/bin:/tmp:${PATH:-}"
ROOT="${RUNTIME_ROOT:-${TB3_APP_ROOT:-/app}}"
BIN="${RUNTIME_BIN:-/tmp/runtime}"
export RUNTIME_ROOT="${ROOT}"
cd "${ROOT}"

if [[ ! -x "${BIN}" ]]; then
  go build -o "${BIN}" ./cmd/runtime
fi

"${BIN}" recover
echo "recover: wrote state/recovery.json"
