#!/usr/bin/env bash
# Offline reference solve: install the completed chronicle, rules, probe,
# assemble lane, attestation, and filter lanes, then rebuild the Go binary
# with vendored modules only (no network), then smoke the HTTP probe/assemble
# path against the bundled labyrinth world.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES="${ROOT_DIR}/files"

cd /app

install -m 0644 "${FILES}/internal/chronicle/resolve.go" internal/chronicle/resolve.go
install -m 0644 "${FILES}/internal/rules/rules.go" internal/rules/rules.go
install -m 0644 "${FILES}/internal/probe/probe.go" internal/probe/probe.go
install -m 0644 "${FILES}/internal/hintassemble/hintassemble.go" internal/hintassemble/hintassemble.go
install -m 0644 "${FILES}/internal/attest/attest.go" internal/attest/attest.go
install -m 0644 "${FILES}/internal/filters/filters.go" internal/filters/filters.go
install -m 0644 "${FILES}/internal/scratchcheck/scratchcheck.go" internal/scratchcheck/scratchcheck.go

PATH="/usr/local/go/bin:${PATH}"
CGO_ENABLED=0
export PATH CGO_ENABLED

test -f go.mod
test -d vendor
mkdir -p /app/bin /app/hint-scratch
/app/scripts/build.sh
test -x /app/bin/labyrinth-oracle

bash "${ROOT_DIR}/oracle_dryrun.sh"

echo "labyrinth-oracle: solution installed, rebuilt, and smoke-checked"
