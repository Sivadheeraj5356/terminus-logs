#!/bin/bash
set -euo pipefail

cp /solution/merkle.rs /app/src/merkle.rs
cp /solution/sync.rs /app/src/sync.rs
cp /solution/sequence.rs /app/src/sequence.rs
cd /app && cargo build --release --bin scenetest
install -m 0755 /app/target/release/scenetest /app/bin/scenetest
echo "Merkle CRDT sync stack installed"
