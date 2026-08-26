#!/bin/bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:/usr/local/go/bin:/app/bin:${PATH}"
cd "$(dirname "${BASH_SOURCE[0]}")"

patch -d /app/environment -p0 < patches/oxk_src_bind.rs.patch
patch -d /app/environment -p0 < patches/oxk_src_pump.rs.patch
patch -d /app/environment -p0 < patches/internal_triage_rank.go.patch
patch -d /app/environment -p0 < patches/internal_surf_emit.go.patch
patch -d /app/environment -p0 < patches/internal_ledger_pump.go.patch
patch -d /app/environment -p0 < patches/internal_route_tie.go.patch
patch -d /app/environment -p0 < patches/internal_peers_share.go.patch

install -D -m 0644 fixed/lane_book.go /app/environment/internal/lane/book.go
install -D -m 0644 fixed/pipeline.go /app/environment/internal/orchestrate/pipeline.go
install -D -m 0644 fixed/run.go /app/environment/internal/runner/run.go
install -D -m 0644 fixed/cap_audit.go /app/environment/internal/cap/audit.go
install -D -m 0644 fixed/epoch_stamp.go /app/environment/internal/epoch/stamp.go

cd /app/environment/oxk && cargo build --release --locked
cp target/release/oxk-cli /app/bin/oxk-cli
cd /app/environment && go build -o /app/bin/splicectl ./cmd/splicectl

/app/bin/splicectl reset
/app/bin/splicectl run eq_pacific
/app/bin/splicectl run eq_priority
/app/bin/splicectl run eq_regen_gap
/app/bin/splicectl run eq_cap_bind
/app/bin/splicectl run eq_path_tie
/app/bin/splicectl run eq_cool_stress
/app/bin/splicectl status
/app/bin/splicectl publish
