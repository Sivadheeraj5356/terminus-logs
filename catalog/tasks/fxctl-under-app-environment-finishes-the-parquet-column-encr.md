# fxctl under `/app/environment` finishes the parquet column encryption metadata d

Submission: `5eebc7cb-8880-4787-9636-dd8fb5c7d563`  
Slug: `fxctl-under-app-environment-finishes-the-parquet-column-encr`  
Latest archive: `5eebc7cb-8880-4787-9636-dd8fb5c7d563_submission_2026-07-15T17_02_42.925Z.zip`  
Revisions in Dropbox: 1

## Task summary

fxctl under `/app/environment` finishes the parquet column encryption metadata desk. The desk reads encrypted column blobs from `/app/environment/payload/`, resolves lane authority and column-key epochs from the durable ring at `/app/environment/payload/ring_seg.bin`, unwraps segment bytes with per-group AAD plus key material, and writes `/app/output/sync_record.json`.

Required artifacts include: `/app/environment`, `/app/environment/payload/`, `/app/environment/payload/ring_seg.bin`, `/app/output/sync_record.json`, `/app/environment/payload/cases.json`, `/app/environment/docs/runbook.md`, `/app/environment/docs/footer_contract.md`, `/app/environment/contracts/sync_record.schema.json`.

Author anonymous tagged this **hard** security task (go, parquet, column-encryption, crypto, aad, keystore).

Time estimates: expert ~60 min, junior ~180 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `5eebc7cb-8880-4787-9636-dd8fb5c7d563_submission_2026-07-15T17_02_42.925Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
