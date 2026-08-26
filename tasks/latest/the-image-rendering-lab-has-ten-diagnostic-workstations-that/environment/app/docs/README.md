# Diagnostic workstation compliance harness

This directory holds the offline compliance harness for the image-rendering
diagnostic workstations. The harness combines a DuckDB inventory, an OPA
policy runner, and a golden-plan comparison to produce a per-workstation
remediation plan that a lab operator applies during a diagnostic session.

## Layout

- `postmortem/postmortem.md` — the authoritative reference. All decision-matrix
  rules live here. Read this first.
- `inventory/workstations.csv` — the seed data used at container build time.
- `inventory/workstations.duckdb` — the built DuckDB. Read-only for the solver.
- `harness/build_inventory.py` — one-shot builder that produces the DuckDB
  from the CSV. Runs at Dockerfile build time.
- `harness/load_facts.py` — projects one workstation row to JSON on stdout.
- `harness/run_policy.sh` — invokes OPA against `/app/policy/*.rego` with
  facts from `load_facts.py` and prints the plan as `{workstation_id, actions}`.
- `harness/diff_plan.py` — compares an emitted plan to a golden.
- `policy/` — where the submitted Rego library goes. Ships empty.
- `golden/plan_ws001.json` … `plan_ws010.json` — the ten reference plans.
- `fixtures/{tiff,png,mp4}/sample.<ext>` — the workload fixtures.

## Query contract

The OPA query the harness issues is `data.workstation.plan.actions`. The
input is `{"workstation": { ...v_workstation projection... }}`. The result
must be an ordered array of action strings matching the canonical order
documented in Section 10 of the postmortem.

## Manual smoke test

    python3 /app/harness/load_facts.py ws-001
    bash   /app/harness/run_policy.sh   ws-001
    python3 /app/harness/diff_plan.py <(bash /app/harness/run_policy.sh ws-005) /app/golden/plan_ws005.json
