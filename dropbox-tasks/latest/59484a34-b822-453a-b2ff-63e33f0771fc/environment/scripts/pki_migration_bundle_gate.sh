#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-}"
if [[ -z "${ROOT}" || ! -d "${ROOT}" ]]; then
  echo "pki_migration_bundle_gate: bundle root required" >&2
  exit 2
fi
required=(
  bundle_meta.json
  ct_logs/b161aa7f_entries.jsonl
  ct_logs/sth.json
  revocations.json
  issuance.json
  manifests/bundle.sha256
  manifests/files.txt
)
for f in "${required[@]}"; do
  if [[ ! -e "${ROOT}/${f}" ]]; then
    echo "pki_migration_bundle_gate: missing ${f}" >&2
    exit 1
  fi
done
manifest="${ROOT}/manifests/bundle.sha256"
while read -r line; do
  want="${line%% *}"
  rel="${line#* }"
  path="${ROOT}/${rel}"
  if [[ ! -f "${path}" ]]; then
    echo "pki_migration_bundle_gate: manifest row missing file ${rel}" >&2
    exit 1
  fi
  got=$(sha256sum "${path}" | awk '{print $1}')
  if [[ "${got}" != "${want}" ]]; then
    echo "pki_migration_bundle_gate: digest mismatch ${rel}" >&2
    exit 1
  fi
done < "${manifest}"
# File list rows may include spaces, so keep the read loop quoted.
while IFS= read -r f; do
  if [[ ! -f "${ROOT}/${f}" ]]; then
    echo "pki_migration_bundle_gate: files.txt entry missing ${f}" >&2
    exit 1
  fi
done < "${ROOT}/manifests/files.txt"
echo "pki_migration_bundle_gate: ok ${ROOT}"
