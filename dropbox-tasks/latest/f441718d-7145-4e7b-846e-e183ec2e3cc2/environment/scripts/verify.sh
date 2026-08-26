#!/usr/bin/env bash
# Verification + certificate status check.
set -euo pipefail

export PATH="/usr/local/go/bin:/usr/local/bin:/tmp:${PATH:-}"
ROOT="${RUNTIME_ROOT:-${TB3_APP_ROOT:-/app}}"
BIN="${RUNTIME_BIN:-/tmp/runtime}"
export RUNTIME_ROOT="${ROOT}"
cd "${ROOT}"

if [[ ! -x "${BIN}" ]]; then
  go build -o "${BIN}" ./cmd/runtime
fi

"${BIN}" verify
"${BIN}" certificate

python3 - <<'PY'
import json, os, sys
root = os.environ.get("RUNTIME_ROOT", "/app")
cert = json.load(open(os.path.join(root, "output", "certificate.json")))
status = json.load(open(os.path.join(root, "output", "certificate_status.json")))
report = json.load(open(os.path.join(root, "output", "verification.json")))
ok = (
    status.get("valid") is True
    and report.get("lineage_ok") is True
    and report.get("graph_ok") is True
    and report.get("checkpoint_ok") is True
    and report.get("replay_ok") is True
    and report.get("hash_ok") is True
    and bool(cert.get("signature"))
    and bool(cert.get("replay_hash"))
)
print("verify: certificate_valid=", status.get("valid"), "report_ok=", ok)
sys.exit(0 if ok else 1)
PY
