#!/usr/bin/env bash
set -euo pipefail

DIGEST="/workspace/output/dependency-digest.txt"
CHECKSUM="/workspace/output/digest-checksum.sha256"

if [[ -n "${IRIS_PROV_SKIP_INTERNAL_PHPUNIT:-}" ]]; then
  echo "IRIS_PROV_SKIP_INTERNAL_PHPUNIT is set" >&2
  exit 1
fi

if [[ ! -f "${DIGEST}" || ! -f "${CHECKSUM}" ]]; then
  echo "digest checksum mismatch" >&2
  exit 1
fi

ACTUAL_SHA="$(tr -d '\n' < "${CHECKSUM}")"
COMPUTED_SHA="$(sha256sum "${DIGEST}" | awk '{print $1}')"
if [[ "${ACTUAL_SHA}" != "${COMPUTED_SHA}" ]]; then
  echo "digest checksum mismatch" >&2
  exit 1
fi

echo "provenance verify ok"
