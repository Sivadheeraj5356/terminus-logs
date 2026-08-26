#!/bin/bash
set -euo pipefail

cd /app

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p /app/cmd/ovpub /app/internal/kvfold /app/bin /app/output

install -m 0644 "${ROOT_DIR}/go/cmd/ovpub/main.go" /app/cmd/ovpub/main.go
install -m 0644 "${ROOT_DIR}/go/internal/kvfold/kvfold.go" /app/internal/kvfold/kvfold.go

bash /app/scripts/compile_report.sh

python3 - <<'PY'
import json
import re
from pathlib import Path

report_path = Path("/app/output/closure_report.json")
doc = json.loads(report_path.read_text(encoding="utf-8"))
schema_mark = int(Path("/app/stubs/revision_stamp.txt").read_text(encoding="utf-8").strip())
assert doc["schema_mark"] == schema_mark
assert isinstance(doc["tenants"], dict)
allowed = {"effective_digest_hex", "resolved_key_count", "overlay_drifted"}
for block in doc["tenants"].values():
    assert set(block.keys()) == allowed
    assert re.fullmatch(r"[0-9a-f]{64}", str(block["effective_digest_hex"]))
    assert isinstance(block["resolved_key_count"], int)
    assert isinstance(block["overlay_drifted"], bool)

manifest_ids = {row["id"] for row in json.loads(Path("/app/data/tenant_registry.json").read_text(encoding="utf-8"))["tenants"]}
assert set(doc["tenants"]) == manifest_ids

beta = doc["tenants"]["tenant_beta"]
alpha = doc["tenants"]["tenant_alpha"]
omicron = doc["tenants"]["tenant_omicron"]
sigma = doc["tenants"]["tenant_sigma"]
tau = doc["tenants"]["tenant_tau"]
upsilon = doc["tenants"]["tenant_upsilon"]
phi = doc["tenants"]["tenant_phi"]

if beta["overlay_drifted"] == alpha["overlay_drifted"]:
    raise SystemExit("oracle smoke: tenant_beta and tenant_alpha share overlay_drifted polarity")
if beta["resolved_key_count"] <= alpha["resolved_key_count"]:
    raise SystemExit("oracle smoke: tenant_beta key count not above tenant_alpha")
if omicron["overlay_drifted"] != alpha["overlay_drifted"]:
    raise SystemExit("oracle smoke: tenant_omicron drift flag diverges from tenant_alpha fuse-only baseline")
if sigma["overlay_drifted"] == omicron["overlay_drifted"]:
    raise SystemExit("oracle smoke: tenant_sigma drift flag matches fuse-only omicron")
if tau["resolved_key_count"] < 3:
    raise SystemExit("oracle smoke: tenant_tau lost dotted alias keys")
if upsilon["resolved_key_count"] != 2:
    raise SystemExit("oracle smoke: tenant_upsilon key count drift")
if phi["resolved_key_count"] < 4:
    raise SystemExit("oracle smoke: tenant_phi lost fused keys")
if phi["overlay_drifted"] == omicron["overlay_drifted"]:
    raise SystemExit("oracle smoke: tenant_phi drift flag matches omicron fuse-only row")
PY
