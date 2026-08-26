#!/usr/bin/env bash
set -euo pipefail
SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCHES="$SOLUTION_DIR/patches"
APP="/app"
cp "$PATCHES/proxyclient.go" "$APP/go/modgate/internal/proxyclient/proxyclient.go"
cp "$PATCHES/policy.go" "$APP/go/modgate/internal/policy/policy.go"
cp "$PATCHES/pipeline.go" "$APP/go/modgate/internal/pipeline/pipeline.go"
cp "$PATCHES/digest.go" "$APP/go/modgate/internal/digest/digest.go"
cp "$PATCHES/annex.go" "$APP/go/modgate/internal/annex/annex.go"
cp "$PATCHES/sumscan.go" "$APP/go/modgate/internal/sumscan/sumscan.go"
cp "$PATCHES/retractmatch_main.rs" "$APP/rust/retractmatch/src/main.rs"
cp "$PATCHES/gofloor_main.rs" "$APP/rust/gofloor/src/main.rs"
bash "$APP/scripts/build.sh"
