#!/usr/bin/env bash
set -euo pipefail
file="${1:-/output/drift.jsonl}"
if [[ ! -f "$file" ]]; then
  echo "missing: $file" >&2
  exit 1
fi
line=0
while IFS= read -r row || [[ -n "$row" ]]; do
  line=$((line + 1))
  if [[ -z "$row" ]]; then
    echo "empty line $line" >&2
    exit 1
  fi
  printf '%s' "$row" | jq -e . >/dev/null || {
    echo "invalid json at line $line" >&2
    exit 1
  }
done < "$file"
echo "ok: $line records"
