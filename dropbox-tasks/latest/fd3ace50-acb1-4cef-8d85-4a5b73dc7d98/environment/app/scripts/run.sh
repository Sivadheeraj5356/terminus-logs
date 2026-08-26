#!/bin/bash
set -euo pipefail

EVIDENCE_DIR="${1:-/app/evidence}"
OUTPUT_DIR="${2:-/app/output}"

mkdir -p "$OUTPUT_DIR"

cd /app
make -s

./bin/vlan-segmentation-enforce "$EVIDENCE_DIR" "$OUTPUT_DIR"

if [ -f "$OUTPUT_DIR/enforcement_result.json" ]; then
    echo "Enforcement analysis completed successfully."
    echo "Results written to: $OUTPUT_DIR/enforcement_result.json"
else
    echo "ERROR: Output file not generated." >&2
    exit 1
fi
