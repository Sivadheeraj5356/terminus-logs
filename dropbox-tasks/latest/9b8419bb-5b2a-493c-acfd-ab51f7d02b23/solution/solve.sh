#!/bin/bash
set -euo pipefail

export PATH="/usr/local/go/bin:/usr/local/cargo/bin:/app/bin:${PATH:-}"

cd /app/environment
PATCH_FILE="/solution/fix.patch"
if [ ! -f "$PATCH_FILE" ]; then
  PATCH_FILE="../solution/fix.patch"
fi
if [ ! -f "$PATCH_FILE" ]; then
  echo "fix.patch not found" >&2
  exit 1
fi
if ! patch -p1 -R --dry-run --silent --force < "$PATCH_FILE" 2>/dev/null; then
  patch -p1 --force < "$PATCH_FILE"
fi

gofmt -w \
  lib/intake/load.go \
  lib/cstore/store.go \
  lib/cstore/commit.go \
  lib/judge/pick.go \
  lib/ix/bridge.go \
  lib/driver/assess.go \
  lib/render/write.go \
  lib/model/types.go \
  cmd/boardctl/main.go

cargo build --release --locked --manifest-path z4/Cargo.toml
cp z4/target/release/ixcore /app/bin/ixcore
go build -o /app/bin/boardctl ./cmd/boardctl

mkdir -p /tmp/board-smoke
/app/bin/boardctl review \
  --record /app/environment/data/orbital_beta \
  --policy /app/environment/data/policy_standard.json \
  --out /tmp/board-smoke \
  --state /tmp/board-smoke/state.json \
  --reset-state
