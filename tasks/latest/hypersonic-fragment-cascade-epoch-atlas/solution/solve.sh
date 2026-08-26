#!/usr/bin/env bash
set -eu
APP_ROOT=/app
PATCH_SRC="$(cd "$(dirname "$0")/files/src" && pwd)"

for rel in \
  ingest/load.ts \
  staging/write.ts \
  kepler/propagate.ts \
  collision/detect.ts \
  spawn/fragments.ts \
  drag/flare.ts \
  export/atlas.ts \
  export/ledger.ts \
  bin/export.ts
do
  install -m 0644 "${PATCH_SRC}/${rel}" "${APP_ROOT}/src/${rel}"
done

( cd "${APP_ROOT}" && bash tooling/build.sh )
mkdir -p "${APP_ROOT}/state" "${APP_ROOT}/output"
