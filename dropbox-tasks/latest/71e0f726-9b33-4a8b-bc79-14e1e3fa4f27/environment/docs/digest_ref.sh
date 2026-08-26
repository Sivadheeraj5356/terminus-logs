#!/usr/bin/env bash
# Reference digest helper for k9_trace chain_fingerprint and WAL CRC.
set -euo pipefail

VERIFIER_PY="${VERIFIER_PY:-/opt/verifier-venv/bin/python3}"

usage() {
  echo "usage: digest_ref.sh chain <sorted-lines-file>" >&2
  echo "       digest_ref.sh crc <payload>" >&2
  exit 1
}

case "${1:-}" in
  chain)
    file="${2:-}"
    if [[ -z "$file" || ! -f "$file" ]]; then
      usage
    fi
    openssl dgst -sha256 "$file" | awk '{print $2}'
    ;;
  crc)
    payload="${2:-}"
    if [[ -z "$payload" ]]; then
      usage
    fi
    "$VERIFIER_PY" -c 'import sys, zlib; print(zlib.crc32(sys.argv[1].encode()) & 0xFFFFFFFF)' "$payload"
    ;;
  *)
    usage
    ;;
esac
