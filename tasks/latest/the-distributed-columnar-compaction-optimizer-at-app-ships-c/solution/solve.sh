#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for name in catalog.cpp normalize.cpp row_overlap.cpp graph.cpp hash.cpp plan_builder.cpp validate.cpp repair.cpp scan_cost.cpp fragmentation.cpp replica.cpp partition.cpp ingest_chain.cpp export_stage.cpp span_rollup.cpp staging_io.cpp ingest_stage.cpp; do
  cp "${SCRIPT_DIR}/files/${name}" "/app/src/${name}"
done

make -C /app clean all
