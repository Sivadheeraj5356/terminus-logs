#!/usr/bin/env bash
set -euo pipefail

cd /app/environment
go build -o /app/bin/claimdocketaudit ./cmd/claimdocketaudit
mkdir -p /app/bin /app/out /app/var /logs/verifier

bash /app/solution/solve.sh

uvx -p 3.13 -w pytest==8.4.1 -w crc32c==2.7.1 pytest /tests/test_outputs.py -rA
