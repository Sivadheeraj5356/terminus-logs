#!/bin/bash
set -euo pipefail

export PATH="$PATH:/usr/local/go/bin:/usr/local/bin"
export GOCACHE=/tmp/gocache-solve
export GOPATH=/tmp/gopath-solve
export GOFLAGS=-buildvcs=false
export HOME="${HOME:-/tmp}"

cd /app

# Survey the project first: entry point, current comparator, and the reference
# orderings the catalog expects.
ls -la /app
cat /app/go.mod
cat /app/cmd/formula-order/main.go
cat /app/internal/version/version.go
head -30 /app/examples.json

# The comparator has to reproduce Homebrew's formula version ordering: the
# string is scanned into typed tokens (alpha/beta/pre/rc words, patch and post
# markers, numeric runs, letter runs) with ordered patterns, tokens compare by
# class precedence with their embedded revision numbers, mismatched classes
# fall back to raw text, and the walk treats trailing zero components as
# nothing. Apply that implementation to internal/version/version.go.
patch -p1 < /solution/fix.patch

go build -o /app/formula-order ./cmd/formula-order
go test ./...

# Smoke-check a few of the reference orderings.
./formula-order 1.2rc2 1.2        # older: prints -1
./formula-order 1.2 1.2a          # letter revision is newer: prints -1
./formula-order 1.2.0 1.2         # trailing zero component: prints 0
./formula-order 2.0 1.9           # prints 1
