#!/usr/bin/env bash
set -euo pipefail
cd /app
# Verifier harness may set this after oracle install so rebuild.sh still runs and
# refreshes compiler-epoch.json (rebuild_nonce) without recompiling stubs over bins.
if [[ "${KVTILE_VERIFIER_EPOCH_ONLY:-0}" == "1" ]]; then
  bash /app/scripts/write-compiler-epoch.sh "${KVTILE_APP_ROOT:-/app}/config/attn-profile.json" rebuild
  exit 0
fi
cargo build --release --locked
install -m 0755 /app/target/release/kvtile-plan /app/bin/kvtile-plan
install -m 0755 /app/target/release/kvtile-advance /app/bin/kvtile-advance
install -m 0755 /app/target/release/kvtile-seal /app/bin/kvtile-seal
bash /app/scripts/write-compiler-epoch.sh "${KVTILE_APP_ROOT:-/app}/config/attn-profile.json" rebuild
