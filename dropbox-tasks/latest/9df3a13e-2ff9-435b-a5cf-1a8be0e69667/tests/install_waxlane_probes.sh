#!/usr/bin/env bash
set -euo pipefail
SRC="${1:-/tests/probe-court}"
DST="/opt/verifier-fixtures/court-probes"
mkdir -p "${DST}"
cp -a "${SRC}/." "${DST}/"
