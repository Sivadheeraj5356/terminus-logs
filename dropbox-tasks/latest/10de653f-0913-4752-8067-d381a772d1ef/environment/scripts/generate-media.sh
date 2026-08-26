#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-/app/fixtures/media-cache/bbb-sample.mp4}"
mkdir -p "$(dirname "$OUT")"
ffmpeg -y -f lavfi -i "testsrc=size=320x240:rate=15" -f lavfi -i "sine=frequency=440:sample_rate=44100" \
  -t 4 -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$OUT"
