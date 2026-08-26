#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if patch --dry-run -d /app/environment -p1 < oracle.patch >/dev/null 2>&1; then
    patch -d /app/environment -p1 < oracle.patch
elif patch --dry-run -R -d /app/environment -p1 < oracle.patch >/dev/null 2>&1; then
    :
else
    echo "oracle patch does not match the supplied source" >&2
    exit 1
fi

cd /app/environment
cargo build --release --locked --offline
mkdir -p /app/bin /app/output
install -m 0755 /app/target/release/forest-audit /app/bin/forest-audit
/app/bin/forest-audit
