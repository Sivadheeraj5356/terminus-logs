#!/usr/bin/env bash
set -euo pipefail

cd /app

SOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "${SOL_DIR}/resolver.go" /app/engine/solver/resolver.go

make build

test -x /app/bin/contact-resolver
test "$(wc -c < /app/bin/contact-resolver | tr -d ' ')" -gt 2048

mkdir -p /app/results
rm -f /app/results/contact_stability_report.json
/app/bin/contact-resolver
test -s /app/results/contact_stability_report.json
