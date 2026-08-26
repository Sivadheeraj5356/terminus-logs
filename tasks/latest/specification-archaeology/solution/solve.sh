#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for required in \
  evidence/incident.json \
  authorities/trust_policy.md \
  authorities/quorum_policy.md \
  authorities/containment_policy.md \
  contracts/evidence_contract.md \
  contracts/assessment_contract.md \
  contracts/containment_contract.md \
  contracts/commitment_contract.md \
  cases/primary_compromise.json \
  cases/quorum_independence_failure.json \
  cases/retroactive_revocation.json \
  cases/emergency_exception_scope.json
do
  test -f "/app/environment/${required}"
done

cp "${ROOT_DIR}/engine.py" /app/environment/adjudicator.py
chmod +x /app/environment/adjudicator.py
rm -rf /app/out
/app/environment/run.sh

python3 - <<'PY'
import json
from pathlib import Path

root = Path("/app/out")
expected = {
    "baseline_compromise",
    "quorum_independence_failure",
    "retroactive_revocation",
    "emergency_exception_scope",
}
if {path.name for path in root.iterdir() if path.is_dir()} != expected:
    raise SystemExit("profile output partition is incomplete")
for name in sorted(expected):
    folder = root / name
    assessment = json.loads((folder / "trust_assessment.json").read_text())
    plan = json.loads((folder / "containment_plan.json").read_text())
    commitment = (folder / "decision_commitment.bin").read_bytes()
    if assessment["profile"] != name or plan["profile"] != name:
        raise SystemExit(f"profile mismatch: {name}")
    if not assessment["assessments"]:
        raise SystemExit(f"empty assessment: {name}")
    if not plan["execution_order"]:
        raise SystemExit(f"empty execution order: {name}")
    if len(commitment) != 104 or not commitment.startswith(b"INC8821\0"):
        raise SystemExit(f"invalid commitment envelope: {name}")
PY
