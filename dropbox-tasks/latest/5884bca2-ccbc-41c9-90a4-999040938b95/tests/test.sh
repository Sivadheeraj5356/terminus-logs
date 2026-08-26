#!/bin/bash
if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile."
  mkdir -p /logs/verifier
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi
mkdir -p /logs/verifier
cd /app
export CARGO_NET_OFFLINE=true
export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"
export PATH="/usr/local/cargo/bin:$PATH"
python3 -m pytest -rA /tests/test_outputs.py
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
