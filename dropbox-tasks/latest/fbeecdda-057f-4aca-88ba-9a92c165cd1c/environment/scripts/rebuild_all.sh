#!/bin/bash
set -euo pipefail
ENV_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ENV_ROOT"
cargo build --release --offline
cp target/release/denscore /app/bin/denscore
go build -o /app/bin/cinecont ./cmd/cinecont
