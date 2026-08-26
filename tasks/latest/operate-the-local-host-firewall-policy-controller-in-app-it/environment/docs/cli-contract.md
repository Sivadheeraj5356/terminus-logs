# CLI contract

Invoke the control tool at `/app/environment/bin/nxctl` (also installed at `/app/bin/nxctl`). Use `--state-dir` for writable state.

Default durable paths:

- `/app/state/backend.json`
- `/app/state/ownership-manifest.json`
- `/app/state/runtime-overrides.json`
- `/app/state/audit.jsonl`

Rebuild after source changes with `cargo build --release` under `/app/environment`.

The bundled demo packet for simulation is `/app/fixtures/packet-allow.json`.

## Status

`nxctl status --json` returns:

- `schema_version` (number)
- `ok` (boolean): true after successful apply or recover on converged state; false when validation rejects the effective configuration without mutation
- `phase` (string)
- `generation` (number)
- `pending_generation` (optional number)
- `managed_rules` (number)
- `foreign_rules` (number)
- `reason_codes` (array of strings)

## Simulation

`nxctl simulate --packet <path> --repeat <count> --json` evaluates packet objects with `src`, `dst`, `dst_port`, and `proto`, returning `verdict` and optional `matched_rule`.

Effective configuration uses tenant `sets` such as `web-clients` with `members`, plus ordered `rules` such as `allow-web` with `action`, `ordered_index`, and optional `dst_port`. Backend snapshots track `next_handle` and per-rule `counter` values.

## Audit

Audit records in `/app/state/audit.jsonl` include `operation`, `phase`, `outcome`, and `reason_code`.

## Failpoints

Optional `NX_FAILPOINT` exposes crash barriers documented in `/app/docs/reconciliation-contract.md`.

The platform verifier runs `python -m pytest` with `--ctrf /logs/verifier/ctrf.json`.

Exit code `0` means success. Nonzero means validation or failpoint failure without claiming success.

## Verifier helpers

Verifier-only helpers (`ref_model`, `backend_factory`, `fixture_generator`) and Python `hashlib` / `random` are used for deterministic scenario generation and are not part of the repair surface. The environment digest helper in `/app/scripts/digest_helper.py` documents the same `hashlib` contract.
