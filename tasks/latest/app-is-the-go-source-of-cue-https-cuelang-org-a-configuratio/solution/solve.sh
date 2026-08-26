#!/bin/bash
# Oracle solution: install the corrected evaluator sources.
#
# The golang base image has no `patch`, so we drop in the fixed files directly
# (kept alongside this script under fixed/). The fix threads a
# deferred-finalization step through the unification scheduler so that
# partially-evaluated non-rooted (inline) struct nodes are completed and any
# conflict inside them is propagated:
#   - internal/core/adt/sched.go    adds a `scheduler.deferred` list and, in
#                                   runTask, completes each deferred node and
#                                   hoists any resulting error (Bottom).
#   - internal/core/adt/context.go  registers an unfinished non-rooted node on
#                                   that deferred list during evalStateCI.
# Both files are required: context.go alone does not compile (the field lives in
# sched.go), and sched.go alone changes nothing (nothing registers a node).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$DIR/fixed/context.go" /app/internal/core/adt/context.go
cp "$DIR/fixed/sched.go"   /app/internal/core/adt/sched.go

# Sanity: the module must still build offline against the vendored deps.
cd /app && GOFLAGS=-mod=vendor GOPROXY=off GOTOOLCHAIN=go1.25.0 go build ./...
