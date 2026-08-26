#!/usr/bin/env bash
# validate_output.sh — quick validation that the converter produced output
set -euo pipefail

OUTPUT_DIR="/app/output"
REPORT="$OUTPUT_DIR/report.json"

if [ ! -f "$REPORT" ]; then
    echo "ERROR: report.json not found at $REPORT"
    exit 1
fi

HTML_COUNT=$(find "$OUTPUT_DIR" -name "*.html" | wc -l)
if [ "$HTML_COUNT" -eq 0 ]; then
    echo "ERROR: no HTML files found in $OUTPUT_DIR"
    exit 1
fi

echo "Validation passed: $HTML_COUNT HTML files + report.json"
