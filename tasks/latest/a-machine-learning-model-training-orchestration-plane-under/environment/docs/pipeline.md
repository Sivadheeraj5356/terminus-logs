# Pipeline Contracts

Machine-learning training orchestration contracts for the supervised model-training
DAG (feature ingest → train/eval → publish) described in `ml-overview.md`.

## DomainHash

```
DomainHash(domain, payload) = hex(SHA256(domain + "\n" + payload))
```

## Canonical JSON

Object keys sorted ascending recursively; compact separators; no HTML escape;
integers preferred over whole-number floats.

## Policy precedence

Effective policy load order is **defaults → `configs/policy.json` → environment**.
Environment variables are the **final** mutation and must remain in force for stage A
epoch materialization and stage C scheduling. Re-reading or re-unmarshaling the
policy file after applying environment overlays is a contract violation.

Environment variables that override `configs/policy.json`:

- `RUNTIME_MAX_RETRIES`
- `RUNTIME_TIMEOUT_MS`
- `RUNTIME_WORKERS` (comma-separated, sorted ascending for assignment)
- `RUNTIME_SEED`
- `RUNTIME_EPOCH` (RFC3339)
- `RUNTIME_STRICT_MODE`
- `RUNTIME_CHECKPOINT_EVERY`

Default epoch: `2024-06-15T12:00:00Z`.

## Required artifacts after `run`

- `state/normalized.json`
- `state/compiled.json`
- `state/schedule.json`
- `state/execution.json`
- `state/journal.json`
- `state/checkpoints.json`
- `state/recovery.json`
- `state/replay.json`
- `state/verification.json`
- `output/certificate.json`
- `output/verification.json`
- `output/recovery.json`
- `output/replay.json`

## Determinism

Repeated clean runs (empty `state/`, `output/`, `cache/`) must produce
byte-identical certificate `body_digest` and `signature` values.
