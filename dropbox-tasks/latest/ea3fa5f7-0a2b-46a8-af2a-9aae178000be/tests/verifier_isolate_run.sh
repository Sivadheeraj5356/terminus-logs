#!/usr/bin/env bash
# Run candidate CLI as nobody with no read access to /tests, /solution, or
# /opt/verifier-fixtures unless an explicit --allow-input path is granted.
set -euo pipefail

ALLOW_INPUTS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --allow-input)
      ALLOW_INPUTS+=("${2:-}")
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -lt 1 ]]; then
  echo "usage: verifier_isolate_run.sh [--allow-input PATH]... -- COMMAND ..." >&2
  exit 2
fi

if ! command -v runuser >/dev/null 2>&1; then
  for candidate in /usr/sbin/runuser /sbin/runuser; do
    if [[ -x "$candidate" ]]; then
      PATH="$(dirname "$candidate"):${PATH}"
      export PATH
      break
    fi
  done
fi
if ! command -v runuser >/dev/null 2>&1; then
  echo "ERROR: runuser not found (install util-linux)" >&2
  exit 1
fi

lockdown_path() {
  local path="$1"
  if [[ ! -e "$path" ]]; then
    return 0
  fi
  if ! chmod -R go-rwx "$path"; then
    echo "ERROR: lockdown chmod failed for ${path} (fail-closed)" >&2
    exit 1
  fi
}

lockdown_path /tests
lockdown_path /opt/verifier-fixtures
if [[ -d /solution ]]; then
  lockdown_path /solution
fi

if runuser -u nobody -- test -r /tests/test_outputs.py 2>/dev/null; then
  echo "ERROR: /tests still readable by nobody after lockdown" >&2
  exit 1
fi

for raw_allow in "${ALLOW_INPUTS[@]}"; do
  if [[ -z "$raw_allow" ]]; then
    continue
  fi
  REAL_ALLOW="$(readlink -f "$raw_allow")"
  if [[ "$REAL_ALLOW" == /opt/verifier-fixtures* ]]; then
    if ! chmod o+rx /opt/verifier-fixtures; then
      echo "ERROR: failed to grant fixture root for allow-input" >&2
      exit 1
    fi
    if ! chmod -R o+rx "$REAL_ALLOW"; then
      echo "ERROR: failed to grant allow-input path ${REAL_ALLOW}" >&2
      exit 1
    fi
  fi
done

chmod o+rx /app /app/bin /app/lib /app/docs /app/data /app/scripts /app/helpers /app/policies 2>/dev/null || true
chmod -R o+rx /app/bin /app/lib /app/docs /app/data /app/scripts /app/helpers /app/policies 2>/dev/null || true
chmod o+rx /opt/verifier-scripts 2>/dev/null || true
chmod o+rx /opt/verifier-scripts/* 2>/dev/null || true

mkdir -p /app/state /app/output
chown -R nobody:nogroup /app/state /app/output 2>/dev/null \
  || chown -R nobody:nobody /app/state /app/output

export -n PYTHONPATH 2>/dev/null || true
unset PYTHONPATH || true

exec runuser -u nobody -- env -i \
  HOME=/tmp \
  PATH="/app/bin:/usr/bin:/bin" \
  LANG=C.UTF-8 \
  "$@"
