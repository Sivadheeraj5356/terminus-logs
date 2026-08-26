#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_step() {
  printf '[oracle] %s\n' "$1"
}

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "missing required file: $path" >&2
    exit 1
  fi
}

install_fixes() {
  log_step "installing corrected replay modules and 64-bit report interfaces"
  cp "$ROOT_DIR/fixes/tel_replay.h" /app/include/tel_replay.h
  cp "$ROOT_DIR/fixes/tel_journal.h" /app/include/tel_journal.h
  cp "$ROOT_DIR/fixes/tel_report.h" /app/include/tel_report.h
  cp "$ROOT_DIR/fixes/tel_config.c" /app/src/tel_config.c
  cp "$ROOT_DIR/fixes/tel_scan.c" /app/src/tel_scan.c
  cp "$ROOT_DIR/fixes/tel_correlate.c" /app/src/tel_correlate.c
  cp "$ROOT_DIR/fixes/tel_db.c" /app/src/tel_db.c
  cp "$ROOT_DIR/fixes/tel_replay.c" /app/src/tel_replay.c
  cp "$ROOT_DIR/fixes/tel_journal.c" /app/src/tel_journal.c
  cp "$ROOT_DIR/fixes/tel_cli.c" /app/src/tel_cli.c
  cp "$ROOT_DIR/fixes/tel_report.c" /app/src/tel_report.c
  sed -i 's/tel_read_u64_be(key_bytes + 4)/tel_read_u64_be(key_bytes)/' /app/src/tel_keys.c
}

rebuild_binary() {
  log_step "rebuilding telreplay"
  bash /app/scripts/build.sh
  require_file /app/bin/telreplay
}

run_matrix() {
  log_step "running matrix pipeline"
  rm -f /app/output/matrix_report.json /app/output/report_seal.bin
  bash /app/scripts/run_matrix.sh
  require_file /app/output/matrix_report.json
  require_file /app/output/report_seal.bin
}

main() {
  log_step "starting lmdb cursor leak telemetry oracle"
  install_fixes
  rebuild_binary
  run_matrix
  log_step "oracle complete"
}

main "$@"
