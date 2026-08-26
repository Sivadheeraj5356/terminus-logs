#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
exec java -cp "$root/build/diffusion-analyzer.jar:/app/lib/duckdb_jdbc.jar" org.terminus.calc.Main "$@"
