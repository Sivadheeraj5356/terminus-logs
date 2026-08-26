#!/usr/bin/env bash
# Produce the npm tarball from a staged package directory.
# Usage: pack.sh <stage-parent> <output-tgz> <epoch>
set -euo pipefail

STAGE_PARENT="$1"
OUT="$2"
EPOCH="$3"

cd "$STAGE_PARENT"
tar -czf "$OUT" package
