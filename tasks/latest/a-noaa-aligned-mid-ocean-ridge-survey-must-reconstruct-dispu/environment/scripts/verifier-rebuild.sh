#!/bin/bash
set -euo pipefail
cd /app
cargo build --release --locked
