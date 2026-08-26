#!/bin/bash
# Operator helper: check_plan_schema for organizational decision impact planner
set -euo pipefail
cd /app
case "check_plan_schema" in
  check_lattice_schema)
    test -f /app/state/odip/impact_lattice.json
    grep -q odip.lattice.v1 /app/state/odip/impact_lattice.json
    ;;
  check_plan_schema)
    test -f /app/output/decision_impact_plan.json
    grep -q odip.plan.v1 /app/output/decision_impact_plan.json
    ;;
  list_scenarios)
    ls /app/fixtures/scenarios
    ;;
  show_policy_gates)
    cat /app/fixtures/policies/approval_policy.json
    ;;
  validate_holdout_mount)
    test -d /opt/verifier-fixtures/odip-holdout || echo "holdout absent"
    ;;
  stage_dept_merge)
    /app/bin/odip stage --scenario /app/fixtures/scenarios/dept_merge --policy /app/fixtures/policies/approval_policy.json --out /app/state/odip/impact_lattice.json
    ;;
  plan_from_lattice)
    /app/bin/odip plan --lattice /app/state/odip/impact_lattice.json --policy /app/fixtures/policies/approval_policy.json --out /app/output/decision_impact_plan.json
    ;;
  replay_budget_realloc)
    /app/bin/odip run --scenario /app/fixtures/scenarios/budget_realloc --policy /app/fixtures/policies/approval_policy.json
    ;;
  digest_hex_check)
    python3 -c "import json; d=json.load(open('/app/state/odip/impact_lattice.json')); assert len(d['lattice_digest'])==64; int(d['lattice_digest'],16)"
    ;;
esac
