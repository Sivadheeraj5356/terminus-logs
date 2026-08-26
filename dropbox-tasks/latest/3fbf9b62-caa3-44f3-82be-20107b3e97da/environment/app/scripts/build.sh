#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:/usr/local/go/bin:${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
cd /app
mkdir -p bin

cd /app/rust/retractmatch
cargo build --release
cp target/release/retractmatch /app/bin/retractmatch

cd /app/rust/gofloor
cargo build --release
cp target/release/gofloor /app/bin/gofloor

cd /app/go/modgate
CGO_ENABLED=0 go build -o /app/bin/modgate .

chmod +x /app/bin/modgate /app/bin/retractmatch /app/bin/gofloor
ln -sfn /app/bin/modgate /usr/local/bin/modgate
ln -sfn /app/bin/retractmatch /usr/local/bin/retractmatch
ln -sfn /app/bin/gofloor /usr/local/bin/gofloor
