#!/usr/bin/env bash
set -euo pipefail

ORIGIN="example.test"
EPOCH=1735689600
DATA_ROOT="${DATA_ROOT:-/data}"
WORK_ROOT="${WORK_ROOT:-/work}"

for scenario in normal interrupted rollback wrap altorigin; do
  src="${DATA_ROOT}/workflows/${scenario}"
  dst="${WORK_ROOT}/${scenario}"
  rm -rf "${dst}"
  mkdir -p "${dst}/previous" "${dst}/keys"
  cp -a "${src}/publish.toml" "${src}/unsigned.zone" "${src}/inventory.json" \
    "${src}/release-log.jsonl" "${dst}/"
  if [[ -f "${src}/operator-snapshot-v1.json" ]]; then
    cp -a "${src}/operator-snapshot-v1.json" "${dst}/"
  fi
  if [[ -d "${src}/previous" ]]; then
    cp -a "${src}/previous/." "${dst}/previous/"
  fi
  if [[ -d "${src}/keys" ]]; then
    cp -a "${src}/keys/." "${dst}/keys/"
  fi
  if [[ -d "${src}/staging" ]]; then
    cp -a "${src}/staging" "${dst}/"
  fi
  chmod -R u+rwX "${dst}"
done

echo "reset-workflows: copied visible workflows to ${WORK_ROOT}"
