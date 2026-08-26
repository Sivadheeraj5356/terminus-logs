#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
source "${APP_ROOT}/lib/common.sh"
python3 - <<'PY'
import hashlib,json
from pathlib import Path
APP=Path("/app/state")
tide=json.loads((APP/"tide-snapshot.json").read_text())
rov=json.loads((APP/"rov-index.json").read_text())
stg=json.loads((APP/"berth-staging.json").read_text())
cert=json.loads((APP/"transfer-cert.json").read_text())
bind=json.loads((APP/"export-bind.json").read_text())
man=json.loads((APP/"ingest-manifest.json").read_text())
freeze=json.loads((APP/"o2-priority-freeze.json").read_text())
if man.get("bind_hash")!=bind.get("bind_hash"):
    raise SystemExit("bind_hash mismatch")
if man.get("rov_hash")!=bind.get("rov_hash"):
    raise SystemExit("manifest rov_hash mismatch")
if rov.get("rov_hash")!=bind.get("rov_hash"):
    raise SystemExit("rov_hash chain mismatch")
if rov.get("tide_hash")!=tide.get("tide_hash"):
    raise SystemExit("tide_hash chain mismatch")
if cert.get("staging_hash")!=stg.get("staging_hash"):
    raise SystemExit("cert staging_hash mismatch")
if cert.get("tide_hash")!=tide.get("tide_hash"):
    raise SystemExit("cert tide_hash mismatch")
if bind.get("cert_hash")!=cert.get("cert_hash"):
    raise SystemExit("cert_hash chain mismatch")
# Digest must match /app/docs/o2-priority-freeze.md (schema_version, tide_hash, entries only).
expected_freeze=hashlib.sha256(json.dumps({k:freeze[k] for k in ("schema_version","tide_hash","entries")},separators=(",",":"),sort_keys=True).encode()).hexdigest()
if freeze.get("freeze_hash")!=expected_freeze:
    raise SystemExit("freeze_hash mismatch")
if not stg.get("feasible"):
    raise SystemExit("infeasible staging")
if not stg.get("cold_cap_ok"):
    raise SystemExit("cold cap")
PY
