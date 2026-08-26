#!/usr/bin/env bash
set -euo pipefail

export CARGO_HOME=/usr/local/cargo
export PATH="/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

cd /app

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/fix.patch" ]; then
    cp "$SCRIPT_DIR/fix.patch" /app/fix.patch
    if patch --dry-run -p1 < fix.patch >/dev/null 2>&1; then
        patch -p1 < fix.patch
    elif patch --dry-run -R -p1 < fix.patch >/dev/null 2>&1; then
        echo "Oracle patch is already applied"
    else
        echo "Oracle patch does not apply cleanly and is not already applied" >&2
        exit 1
    fi
fi

cargo build --release --workspace --locked --offline

install -m 0755 target/release/nxctl /app/bin/nxctl
install -m 0755 target/release/nxd /app/bin/nxd

cargo test --workspace --offline

/app/bin/nxctl --state-dir /tmp/oracle-smoke reset-demo
NX_FAILPOINT=after-stage-sets /app/bin/nxctl --state-dir /tmp/oracle-smoke apply --json || true
/app/bin/nxctl --state-dir /tmp/oracle-smoke recover --json
