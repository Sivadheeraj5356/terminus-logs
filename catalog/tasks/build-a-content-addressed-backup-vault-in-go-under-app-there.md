# Build a content-addressed backup vault in Go under `/app`. There is no starter c

Submission: `46c2a3b0-a287-4a6d-8389-8a3fbae43b65`  
Slug: `build-a-content-addressed-backup-vault-in-go-under-app-there`  
Latest archive: `46c2a3b0-a287-4a6d-8389-8a3fbae43b65_submission_2026-07-19T05_54_23.145Z.zip`  
Revisions in Dropbox: 5

## Task summary

Build a content-addressed backup vault in Go under `/app`. There is no starter code. Read `/app/data/manifest.json` and each job config, pull the pinned policy material from `/app/data/endpoints.json`, walk each source tree, split file bodies with the gear-table CDC in `/app/spec/SPEC.md`, deduplicate into a shared chunk store, and write the batch plus per-job artifacts including HMAC attestations and the hash-chained ledger. When `/app/resources/remote_catalog/extra_jobs.json` is present, append those jobs after the main manifest. Ship `/app/main.go` and `/app/go.mod`, produce `/app/bin/backup-dedup` as a static binary (`CGO_ENABLED=0`, standard library only), and provide `/app/run.sh` that builds and runs it with empty stdout and stderr. Leave `/app/data/` and `/app/spec/` alone. Identical inputs must yield byte-identical outputs. Internet access is required for the policy fetch.

Required artifacts include: `/app/data/manifest.json`, `/app/data/endpoints.json`, `/app/spec/SPEC.md`, `/app/resources/remote_catalog/extra_jobs.json`, `/app/main.go`, `/app/go.mod`, `/app/bin/backup-dedup`, `/app/run.sh`.

Author anonymous tagged this **hard** security task (content-defined-chunking, hmac, merkle-tree, content-addressed-storage, backup-attestation).

Time estimates: expert ~480 min, junior ~1440 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `46c2a3b0-a287-4a6d-8389-8a3fbae43b65_submission_2026-07-19T05_54_23.145Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
