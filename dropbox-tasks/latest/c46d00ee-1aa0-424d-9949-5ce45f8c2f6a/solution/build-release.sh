#!/bin/bash
set -euo pipefail
cd /app
POLICY=/app/config/metadata-policy.json
export SOURCE_DATE_EPOCH="$(python3 -c "import json; print(json.load(open('$POLICY'))['sourceDateEpoch'])")"
mkdir -p vendor
if [ ! -d vendor/serde ] && [ -f vendor-crates.tar.gz ]; then
  tar xzf vendor-crates.tar.gz -C /app
fi
rm -rf dist output
mkdir -p dist output
export CARGO_NET_OFFLINE=true
cargo build --release --locked --offline --manifest-path /app/Cargo.toml -p metrics-cli
cargo build --release --locked --offline --manifest-path /app/Cargo.toml -p metacycle-cli
BIN=/app/target/release/metrics-cli bash /app/scripts/healthcheck.sh
/app/target/release/metacycle graph --root /app --lock config/graph-lock.csv --out /app/output/dep-graph.json
/app/target/release/metrics-cli --input /app/fixtures/metrics-records.jsonl --out /app/output/metrics-report.json
/app/target/release/metacycle audit \
  --root /app \
  --lock config/graph-lock.csv \
  --order config/graph-order.csv \
  --policy config/metadata-policy.json \
  --out dist/metadata-manifest.json
printf '%s  vendor/serde/Cargo.toml\n' "$(sha256sum vendor/serde/Cargo.toml | awk '{print $1}')" > dist/vendor-lock.sha256
(
  cd dist
  find . -type f ! -name 'checksums.sha256' | sort | while read -r f; do
    rel="${f#./}"
    printf '%s  %s\n' "$(sha256sum "$rel" | awk '{print $1}')" "$rel"
  done
) > dist/checksums.sha256
