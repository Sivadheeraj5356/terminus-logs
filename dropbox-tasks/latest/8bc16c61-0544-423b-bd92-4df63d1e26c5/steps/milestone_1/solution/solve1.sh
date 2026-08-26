#!/bin/bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path

path = Path("/app/tools/build-component.sh")
text = path.read_text()
text = text.replace("wasm32-wasip1", "wasm32-wasip2")
text = text.replace(
    "cargo build --quiet --release -p edge-worker\n",
    "cargo build --quiet --release --target wasm32-wasip2 -p edge-worker\n"
    "cp /app/target/wasm32-wasip2/release/edge-worker.wasm "
    "/app/target/wasm32-wasip2/release/edge_worker.wasm\n",
)
path.write_text(text)
PY

cd /app
/app/tools/build-component.sh
