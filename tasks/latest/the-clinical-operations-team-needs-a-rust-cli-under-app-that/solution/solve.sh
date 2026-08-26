#!/bin/bash
set -euo pipefail

cd /app

cp /solution/src/*.rs /app/src/
find /solution/src -mindepth 2 -name '*.rs' | while read -r file; do
  rel="${file#/solution/src/}"
  cp "$file" "/app/src/${rel}"
done

cargo build --release --locked
./target/release/hospital_analytics --input-dir /app/data --output /app/output/analytics_report.json
