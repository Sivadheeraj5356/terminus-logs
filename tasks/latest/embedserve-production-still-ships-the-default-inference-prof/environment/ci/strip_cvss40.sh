#!/usr/bin/env bash
set -euo pipefail

ROOT="/app/environment/fixtures/rustsec-advisory-db"
if [[ ! -d "$ROOT/crates" ]]; then
  echo "advisory db missing: $ROOT" >&2
  exit 1
fi
while IFS= read -r -d '' file; do
  rm -f "$file"
done < <(grep -rl 'CVSS:4.0' "$ROOT" -z || true)
echo "stripped CVSS 4.0 advisories from $ROOT"
