#!/usr/bin/env bash
# Pack a founder-share zip: static lab + this note + two sample Harbor packages.
# Does not include jobs/, .env, or API keys.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/worlds-lab-founder-share.zip"
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

mkdir -p "$STAGING/lab" "$STAGING/docs" "$STAGING/tasks/latest"
cp "$ROOT/lab/index.html" "$ROOT/lab/lab.css" "$ROOT/lab/lab.js" "$ROOT/lab/corpus.js" "$ROOT/lab/corpus.json" "$STAGING/lab/"
cp "$ROOT/docs/Founder_Share.md" "$STAGING/docs/"
# Two packages so instruction.md / environment links work for the demo rows.
for slug in repair-the-pendulum-motion-solver booking-slot-merge; do
  if [[ -d "$ROOT/tasks/latest/$slug" ]]; then
    mkdir -p "$STAGING/tasks/latest"
    cp -a "$ROOT/tasks/latest/$slug" "$STAGING/tasks/latest/"
  fi
done
printf '%s\n' \
  "Applied Work Worlds Lab (static). From this folder:" \
  "  python -m http.server 8765" \
  "  open http://127.0.0.1:8765/lab/index.html" \
  "See docs/Founder_Share.md" > "$STAGING/README-SHARE.txt"

rm -f "$OUT"
(cd "$STAGING" && zip -qr "$OUT" lab docs tasks README-SHARE.txt)
echo "wrote $OUT ($(wc -c < "$OUT") bytes)"
