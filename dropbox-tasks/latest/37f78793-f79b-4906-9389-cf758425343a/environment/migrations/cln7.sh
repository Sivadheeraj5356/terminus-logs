#!/usr/bin/env bash
set -euo pipefail
settle_file="/app/var/lab/settle_state.json"
journal_file="/app/var/lab/pulse_journal.jsonl"
mkdir -p /app/var/lab
if [[ "${1:-}" == "--restore" && -n "${2:-}" ]]; then
  echo '{"poisoned": false, "pulse_carry": 255}' > "$settle_file"
  exit 0
fi
rm -f "$settle_file"
echo '{"poisoned": true, "pulse_carry": 255}' > "$settle_file"
: > "$journal_file"
