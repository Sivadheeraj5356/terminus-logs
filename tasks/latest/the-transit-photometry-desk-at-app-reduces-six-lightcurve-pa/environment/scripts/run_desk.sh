#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DESK_ROOT="$ROOT"
export PATH="$ROOT/bin:/usr/local/go/bin:${PATH}"
export HOME="${HOME:-/home/model}"
export GOCACHE="${GOCACHE:-$HOME/.cache/go-build}"
export GOMODCACHE="${GOMODCACHE:-$HOME/go/pkg/mod}"
mkdir -p "$GOCACHE" "$GOMODCACHE"
bash "$ROOT/scripts/build.sh"
mkdir -p "$ROOT/output" "$ROOT/work" "$ROOT/legacy"
rm -f "$ROOT/work"/*.bundle
# Prefer the sealed independent legacy binary when present (root-protected).
if [[ -x /opt/verifier/legacy ]]; then
  /opt/verifier/legacy > "$ROOT/legacy/fresh_lane.txt"
else
  "$ROOT/bin/legacy" > "$ROOT/legacy/fresh_lane.txt"
fi
"$ROOT/bin/desk"
