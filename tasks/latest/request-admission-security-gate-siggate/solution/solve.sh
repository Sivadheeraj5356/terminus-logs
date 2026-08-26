#!/bin/bash
set -euo pipefail

export PATH="/usr/local/go/bin:${PATH}"
export CGO_ENABLED=0

APP_ROOT="${APP_ROOT:-/app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d "${SCRIPT_DIR}/files" ]; then
  if [ -d "/solution/files" ]; then
    SCRIPT_DIR="/solution"
  elif [ -d "/task/solution/files" ]; then
    SCRIPT_DIR="/task/solution"
  fi
fi
FILES="${SCRIPT_DIR}/files"

if [ ! -d "${FILES}/internal" ]; then
  echo "oracle: missing solution files under ${FILES}" >&2
  exit 1
fi

cd "${APP_ROOT}" || { echo "oracle: /app not found" >&2; exit 1; }

PATCH_FILES=(
  internal/canonical/canonical.go
  internal/verify/verify.go
  internal/cli/cli.go
  internal/envelope/load.go
  internal/model/model.go
  internal/profile/profile.go
  cmd/siggate/main.go
  go.mod
)

for rel in "${PATCH_FILES[@]}"; do
  src="${FILES}/${rel}"
  if [ ! -f "${src}" ]; then
    echo "oracle: missing patch file ${src}" >&2
    exit 1
  fi
  mkdir -p "$(dirname "${APP_ROOT}/${rel}")"
  cp -a "${src}" "${APP_ROOT}/${rel}"
done

mkdir -p "${APP_ROOT}/bin"
go build -trimpath -o "${APP_ROOT}/bin/siggate" ./cmd/siggate
chmod +x "${APP_ROOT}/bin/siggate"
test -x "${APP_ROOT}/bin/siggate"
