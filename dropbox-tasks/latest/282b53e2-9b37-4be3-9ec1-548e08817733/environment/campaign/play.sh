#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT_DIR:-/app/output}"
BUILD="$ROOT/build"
rm -rf "$BUILD"
mkdir -p "$BUILD" "$OUT/transcripts" "$OUT/state"
mapfile -t SOURCES < <(find "$ROOT/src" -name '*.java' | sort)
javac -encoding UTF-8 -d "$BUILD" "${SOURCES[@]}"
exec java -cp "$BUILD" nxq.campaign.PlayDriver "$ROOT" "$OUT" "$@"
