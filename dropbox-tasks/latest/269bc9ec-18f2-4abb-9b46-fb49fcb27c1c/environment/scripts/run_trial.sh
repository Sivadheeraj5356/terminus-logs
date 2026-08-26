#!/bin/bash
set -euo pipefail
exec java -Dai.djl.offline=true \
  -cp '/app/target/djl-parity-trial-1.0.0.jar:/app/target/dependency/*' \
  org.example.parity.Main \
  --manifest "${MANIFEST:-/app/input/manifest.jsonl}" \
  --policy "${POLICY:-/app/config/parity-policy.json}" \
  --model-dir "${MODEL_DIR:-/app/models/mobilenet-v3-parity}" \
  --source "${MODEL_SOURCE_CONFIG:-/app/config/model-source.properties}" \
  --output "${OUTPUT:-/app/output/parity-report.json}"
