#!/usr/bin/env bash
# Sweep the whole workstation fleet, emit or compare per-workstation plans.
#
# Usage:
#   sweep.sh emit         Emit plans to /tmp/plans/<ws>.json
#   sweep.sh check        Compare emitted plans to /app/golden/plan_<ws>.json.
#                         Exit 0 iff every workstation matches.
set -euo pipefail

MODE="${1:-emit}"
HARNESS="/app/harness"
GOLDEN="/app/golden"
POLICY_DIR="/app/policy"
DB="/app/inventory/workstations.duckdb"
OUT_DIR="/tmp/plans"

if ! ls "${POLICY_DIR}"/*.rego >/dev/null 2>&1; then
    echo "no rego library under ${POLICY_DIR}" >&2
    exit 4
fi

mkdir -p "${OUT_DIR}"

# List of workstation IDs, in stable order.
mapfile -t WS_IDS < <(
    python3 - <<'PY'
import duckdb
con = duckdb.connect("/app/inventory/workstations.duckdb", read_only=True)
for (ws,) in con.execute("SELECT id FROM v_workstation ORDER BY id").fetchall():
    print(ws)
con.close()
PY
)

if [ "${#WS_IDS[@]}" -eq 0 ]; then
    echo "empty inventory" >&2
    exit 3
fi

FAIL_COUNT=0
FAILED_WS=()

for WS in "${WS_IDS[@]}"; do
    PLAN_OUT="${OUT_DIR}/${WS}.json"
    if ! bash "${HARNESS}/run_policy.sh" "${WS}" > "${PLAN_OUT}"; then
        echo "policy run failed for ${WS}" >&2
        FAIL_COUNT=$((FAIL_COUNT + 1))
        FAILED_WS+=("${WS}")
        continue
    fi

    if [ "${MODE}" = "check" ]; then
        GOLDEN_FILE="${GOLDEN}/plan_${WS//-/}.json"
        if ! python3 "${HARNESS}/diff_plan.py" "${PLAN_OUT}" "${GOLDEN_FILE}" 2>/tmp/diff.err; then
            echo "MISMATCH: ${WS}" >&2
            cat /tmp/diff.err >&2 || true
            FAIL_COUNT=$((FAIL_COUNT + 1))
            FAILED_WS+=("${WS}")
        fi
    fi
done

if [ "${FAIL_COUNT}" -gt 0 ]; then
    echo "sweep FAIL: ${FAIL_COUNT} workstation(s) failed: ${FAILED_WS[*]}" >&2
    exit 1
fi

echo "sweep OK: ${#WS_IDS[@]} workstations processed"
exit 0
