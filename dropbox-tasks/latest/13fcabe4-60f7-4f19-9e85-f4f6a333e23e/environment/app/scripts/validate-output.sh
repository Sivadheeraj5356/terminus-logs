#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-/output}"
WORK="${2:-/work/normal}"
ANCHOR="${ANCHOR:-/data/trust-anchors/example.test.anchor}"
SIGNED="${OUT}/example.test.signed"

if [[ ! -f "${SIGNED}" ]]; then
  echo "missing signed zone: ${SIGNED}" >&2
  exit 1
fi

dnssec-verify -o example.test. "${SIGNED}" "${ANCHOR}"
/app/bin/zonepub inspect-manifest --manifest "${OUT}/publication-manifest.json" --format text
jq -e '.schema_version == 2' "${OUT}/publication-manifest.json" >/dev/null
echo "validate-output: ok (${WORK})"
