#!/bin/bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_FILE="${SRC_DIR}/keyring_cutover_gate.go"
DEST_FILE="${APP_DIR}/keyring_cutover_gate.go"

mkdir -p "${APP_DIR}"

if [ "$(readlink -f "${SRC_FILE}")" != "$(readlink -f "${DEST_FILE}")" ]; then
    cp "${SRC_FILE}" "${DEST_FILE}"
fi

gofmt -w "${DEST_FILE}"
go build -o "${APP_DIR}/keyring_cutover_gate" "${DEST_FILE}"
