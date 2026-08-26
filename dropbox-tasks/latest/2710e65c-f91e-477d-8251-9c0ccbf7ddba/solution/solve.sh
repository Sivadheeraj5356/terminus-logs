#!/usr/bin/env bash
set -euo pipefail

# Ensure the Go toolchain is on PATH even under a login shell that does not
# inherit the golang image's profile additions.
export PATH="/usr/local/go/bin:${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
export GOFLAGS="-mod=mod"
export GOPROXY="off"

mkdir -p /app/out /app/project/resolver

# R11: the resolver source belongs at /app/project/resolver/main.go, the
# same fixed path a submission's own resolver belongs at. Build and invoke
# it exactly the way the verifier re-runs it: `go build ./resolver` from
# /app/project, then the built program with a registry dir, a manifest
# path, and a lock output path.
cp /solution/resolver/main.go /app/project/resolver/main.go
( cd /app/project && go build -o /tmp/resolver ./resolver )
/tmp/resolver /app/registry /app/manifest.toml /app/out/lock.json

# R7: writes the compat/telemetrybusv1 adapter for whichever telemetrybus
# version the lockfile above resolved. Free-form by contract, so this is
# its own step rather than folded into the R11 resolver.
go build -o /tmp/writeadapter /solution/writeadapter.go
/tmp/writeadapter

# No standalone build of /app/project is attempted here: the real tree
# never gets a real telemetrybus copy under /app/project/telemetrybus (R8
# reserves that for the verifier's own isolated build check, which vendors
# the registry stub itself). Attempting `go build ./...` against the real
# tree fails on that missing import for reasons unrelated to anything this
# script gets right or wrong.
