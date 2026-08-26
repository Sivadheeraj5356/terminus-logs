#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

require_tree() {
  local missing=0
  for path in \
    "${ROOT_DIR}/vein/claim.go" \
    "${ROOT_DIR}/vein/hold.go" \
    "${ROOT_DIR}/weft/admit.go" \
    "${ROOT_DIR}/drift/width.go" \
    "${ROOT_DIR}/slate/freeze.go" \
    "${ROOT_DIR}/thaw/load.go" \
    "${ROOT_DIR}/rift/barrier.go" \
    "${ROOT_DIR}/spine/segment.go" \
    "${ROOT_DIR}/grove/mix.go"
  do
    if [[ ! -f "${path}" ]]; then
      echo "missing oracle source: ${path}" >&2
      missing=1
    fi
  done
  if [[ "${missing}" -ne 0 ]]; then
    exit 1
  fi
}

install_oracle_sources() {
  cp "${ROOT_DIR}/vein/claim.go" vein/claim.go
  cp "${ROOT_DIR}/vein/hold.go" vein/hold.go
  cp "${ROOT_DIR}/weft/admit.go" weft/admit.go
  cp "${ROOT_DIR}/drift/width.go" drift/width.go
  cp "${ROOT_DIR}/slate/freeze.go" slate/freeze.go
  cp "${ROOT_DIR}/thaw/load.go" thaw/load.go
  cp "${ROOT_DIR}/rift/barrier.go" rift/barrier.go
  cp "${ROOT_DIR}/spine/segment.go" spine/segment.go
  cp "${ROOT_DIR}/grove/mix.go" grove/mix.go
}

rebuild_runner() {
  export PATH="/usr/local/go/bin:${PATH}"
  go build -trimpath -ldflags="-s -w" -o /app/bin/dschedsim ./cmd/dschedsim
  go build -trimpath -ldflags="-s -w" -o /app/bin/sched_probe ./cmd/sched_probe
}

cd /app/environment
require_tree
install_oracle_sources
rebuild_runner
