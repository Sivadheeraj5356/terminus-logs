#!/bin/bash
set -euo pipefail

ROOT="/app/environment"
cd "${ROOT}"

export PATH="/usr/local/cargo/bin:/usr/local/go/bin:${PATH}"

mkdir -p "${ROOT}/bin"

cargo build --release --locked -p mx_sim
cp "${ROOT}/target/release/mx_sim" "${ROOT}/bin/h7_sim"

cd "${ROOT}/s9d"
go build -o "${ROOT}/bin/h7d" ./cmd/h7d
