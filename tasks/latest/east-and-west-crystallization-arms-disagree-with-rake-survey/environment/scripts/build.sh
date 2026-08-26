#!/bin/bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:/usr/local/go/bin:${PATH}"
export CGO_ENABLED=1
export GOFLAGS=-mod=readonly

mkdir -p /app/bin
cd /app/rosegate
cargo build --release --locked 2>/dev/null || cargo build --release
cd /app
go build -trimpath -buildvcs=false -o /app/bin/pond_ctl ./cmd/pond_ctl
go build -trimpath -buildvcs=false -o /app/bin/digest_cli ./tools/digest_cli
