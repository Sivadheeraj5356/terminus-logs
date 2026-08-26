#!/bin/bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:/opt/verifier-venv/bin:/opt/verifier-scripts:/app/bin:${PATH}"
export CARGO_INCREMENTAL=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FILES="${SCRIPT_DIR}/files"

cp "${FILES}/density_mod.rs" /app/src/density/mod.rs
cp "${FILES}/enrichment_mod.rs" /app/src/enrichment/mod.rs
cp "${FILES}/intersect_mod.rs" /app/src/intersect/mod.rs
cp "${FILES}/ingest_mod.rs" /app/src/ingest/mod.rs
cp "${FILES}/atlas_mod.rs" /app/src/atlas/mod.rs

bash /app/scripts/rebuild-assay-ledger.sh
test -x /app/bin/assay-ledger
