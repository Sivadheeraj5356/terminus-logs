#!/usr/bin/env bash
set -euo pipefail

bash /app/scripts/ensure-limits.sh

SCENARIO="${1:-normal}"
EPOCH="${EPOCH:-1784006400}"
WORK="/work/${SCENARIO}"
OUT="/output"
LOG="/logs/${SCENARIO}-repro.log"

mkdir -p /logs "${OUT}"
/app/scripts/reset-workflows.sh >/dev/null

{
  echo "=== repro ${SCENARIO} $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  make -C /app build
  /app/bin/zonepub publish --workspace "${WORK}" --output-dir "${OUT}" --epoch "${EPOCH}"
  echo "--- dnssec-verify ---"
  /app/scripts/validate-output.sh "${OUT}" "${WORK}"
  echo "--- hashes ---"
  sha256sum "${OUT}/example.test.signed" "${OUT}/publication-manifest.json" || true
  echo "--- journal tail ---"
  tail -n 5 "${WORK}/release-log.jsonl" || true
} 2>&1 | tee "${LOG}"

if [[ "${2:-}" == "--resume-only" ]]; then
  /app/bin/zonepub publish --workspace "${WORK}" --output-dir "${OUT}" --epoch "${EPOCH}" | tee -a "${LOG}"
  sha256sum "${OUT}/example.test.signed" "${OUT}/publication-manifest.json" | tee -a "${LOG}"
fi
