# Restore envelope custody qualification in `/app` and publish `/output/recovery-s

Submission: `160a718f-940b-4072-b6cf-373b99176c14`  
Slug: `restore-envelope-custody-qualification-in-app-and-publish-ou`  
Latest archive: `160a718f-940b-4072-b6cf-373b99176c14_submission_2026-07-17T04_24_07.195Z.zip`  
Revisions in Dropbox: 1

## Task summary

Restore envelope custody qualification in `/app` and publish `/output/recovery-set` from `/app/vault` using the cryptographic protocols in `/app/docs`. The completed recovery set must contain recovered objects under `/output/recovery-set/objects`, a path-sorted `/output/recovery-set/inventory.jsonl`, `/output/recovery-set/recovery-root.json`, and `/output/recovery-set/audit.dsse.json` as documented. Qualification must honor historical custody authority at each object's epoch, committed rewrap lineage (including rollbacks), distinct authorized organizations, version-specific envelope identity, complete evidence snapshots, resumable checkpoint safety, source immutability, and atomic publication without provisional plaintext. `/output/recovery-set/recovery-root.json` must include `schema_version`, `policy_id`, `evidence_snapshot_sha256`, `inventory_sha256`, and `recovery_root`. Do not modify `/app/vault`. `/app/bin/vault-inspect` must report the same authoritative committed heads used by `/app/bin/vault-qualify`. `/app/bin/vault-legacy-check` must continue validating supported legacy archives. Rebuild with `cd /app && make clean install` using `GOTOOLCHAIN=local` and `GOFLAGS=-mod=readonly`. Deterministic publication interruptions use `VAULT_QUALIFY_FAILPOINT` values documented in `/app/docs/output-contract.md`; rerun must converge byte-identically.

Required artifacts include: `/output/recovery-set`, `/app/vault`, `/app/docs`, `/output/recovery-set/objects`, `/output/recovery-set/inventory.jsonl`, `/output/recovery-set/recovery-root.json`, `/output/recovery-set/audit.dsse.json`, `/app/bin/vault-inspect`.

Author anonymous tagged this **hard** security task (envelope-encryption, threshold-custody, cryptographic-recovery, rewrap-journal, dsse-audit, atomic-publication).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `160a718f-940b-4072-b6cf-373b99176c14_submission_2026-07-17T04_24_07.195Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
