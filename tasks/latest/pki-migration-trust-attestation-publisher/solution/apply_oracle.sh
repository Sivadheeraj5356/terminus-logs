#!/bin/bash
set -euo pipefail

install -D corrected/internal/bundlewalk/rows.go /app/internal/bundlewalk/rows.go
install -D corrected/internal/trustmatrix/runner.go /app/internal/trustmatrix/runner.go
install -D corrected/internal/ledgerpublish/emit.go /app/internal/ledgerpublish/emit.go
install -D corrected/internal/publishledger/epoch.go /app/internal/publishledger/epoch.go
install -D corrected/cmd/ctpki/main.go /app/cmd/ctpki/main.go
install -D corrected/internal/ctproof/guard.go /app/internal/ctproof/guard.go
install -D corrected/internal/proofgate/review.go /app/internal/proofgate/review.go
install -D corrected/internal/roottrust/store.go /app/internal/roottrust/store.go
install -D corrected/internal/serialdup/winner.go /app/internal/serialdup/winner.go
install -D corrected/internal/sthclock/window.go /app/internal/sthclock/window.go
install -D corrected/internal/manifestdigest/rows.go /app/internal/manifestdigest/rows.go
install -D corrected/internal/revoke/check.go /app/internal/revoke/check.go
install -D corrected/scripts/pki_migration_bundle_gate.sh /app/scripts/pki_migration_bundle_gate.sh
chmod +x /app/scripts/pki_migration_bundle_gate.sh
