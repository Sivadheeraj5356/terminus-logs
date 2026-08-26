#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES="${ROOT_DIR}/files"
APP_ROOT="${APP_ROOT:-/app}"

mkdir -p "${APP_ROOT}/src" "${APP_ROOT}/output" "${APP_ROOT}/state"
cp -R "${FILES}/attestation" "${FILES}/trust" "${FILES}/calutil" "${APP_ROOT}/src/"
cp "${FILES}/release_gate.py" "${APP_ROOT}/src/release_gate.py"

set +e
"${APP_ROOT}/bin/gmp-lot-integrity-attestor" attest-release \
  --metadata "${APP_ROOT}/environment/metadata/base" \
  --stage "${APP_ROOT}/state/batch-release-snapshot.json" \
  --output "${APP_ROOT}/output/batch-release-audit.json"
rc=$?
set -e
# Hold lots exit 1 after writing artifacts; only treat other codes as oracle failure.
if [ "$rc" -ne 0 ] && [ "$rc" -ne 1 ]; then
  exit "$rc"
fi
