#!/bin/bash
set -eu
cd /app
rm -rf dist output
mkdir -p dist output
cargo build --release --manifest-path /app/Cargo.toml -p metrics-cli
cargo build --release --manifest-path /app/Cargo.toml -p metacycle-cli
./target/release/metacycle graph --root /app --out output/dep-graph.json
./target/release/metrics-cli --input fixtures/metrics-records.jsonl --out output/metrics-report.json
./target/release/metacycle audit --root /app --lock config/graph-lock.csv --policy config/metadata-policy.json --out dist/metadata-manifest.json
