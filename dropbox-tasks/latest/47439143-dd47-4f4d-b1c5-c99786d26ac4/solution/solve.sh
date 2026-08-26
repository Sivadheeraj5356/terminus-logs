#!/bin/bash
set -euo pipefail

# Install the differential decision. Everything else in the analyzer scaffold is
# already wired; analyze.rs is the only agent surface.
cp /solution/analyzer/src/analyze.rs /app/environment/analyzer/src/analyze.rs

# Prove it builds before handing over to the verifier.
cd /app/environment
rustc --edition 2021 -O analyzer/src/main.rs -o /tmp/oracle-analyzer

echo "oracle: installed analyzer/src/analyze.rs"
