# hopledger overview

`hopledger` is an offline batch processor for relay-mesh hop journals. It reads NDJSON manifests, merges multi-lane journals, resolves revisions and cancellations, applies latency policy, checkpoints replay state, and emits deterministic shift-close artifacts.

Contract documents:

- `MANIFEST.md` — manifest schema and CLI
- `EVENTS.md` — event grammar and merge ordering
- `POLICY.md` — SLA policy and updates
- `CHECKPOINT.md` — snapshot and resume semantics
- `REPORT.md` — report schema version 3
- `DIGEST.md` — digest canonicalization
- `AUDIT.md` — audit JSONL schema

Build and run examples are in `/app/environment/README.md`.
