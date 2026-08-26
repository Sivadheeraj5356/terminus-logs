#!/bin/bash
set -euo pipefail
/usr/local/zig/zig build -Doptimize=ReleaseSafe
cp /app/zig-out/bin/quorumgate /app/bin/quorumgate
