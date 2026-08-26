#!/bin/sh
set -eu
cd /app
cargo build --release --locked
install -m 0755 target/release/threatcomp /usr/local/bin/threatcomp
