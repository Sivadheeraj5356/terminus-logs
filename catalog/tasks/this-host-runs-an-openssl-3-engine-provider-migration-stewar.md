# This host runs an OpenSSL 3 ENGINE→provider migration steward under `/app/enviro

Submission: `e36bdf4c-bef7-4d73-a5ea-e4c11ac8f88a`  
Slug: `this-host-runs-an-openssl-3-engine-provider-migration-stewar`  
Latest archive: `e36bdf4c-bef7-4d73-a5ea-e4c11ac8f88a_submission_2026-07-16T14_33_33.239Z.zip`  
Revisions in Dropbox: 5

## Task summary

This host runs an OpenSSL 3 ENGINE→provider migration steward under `/app/environment`. Prefer-arm property queries, provider activation order, and URI loader schemes decide which cryptographic arm is authorized to satisfy a case. After migration, the graded matrix still publishes unauthorized outcomes: strict queries fall back off the prefer-arm, first-wins activation order collapses, and `slotA` rows keep the legacy engine URI scheme so material that should require the preferred arm still opens under `eng://`. Mid-cycle arming state under `/app/output/.ov_persist/` can leave a later suite able to seal with a stale nonce or a residue-shaped digest. Contract details live in `/app/environment/docs/ov_contract.md` and `/app/environment/docs/evt_lex.md`.

Required artifacts include: `/app/environment`, `/app/output/.ov_persist/`, `/app/output/ov_trace.json`, `/app/environment/share/ref_blobs/`, `/app/environment/r4/ord.go`, `/app/environment/t6/bind.go`, `/app/environment/docs/ov_contract.md`, `/app/environment/docs/evt_lex.md`.

Author anonymous tagged this **hard** security task (openssl, provider, engine, crypto-authority, access-control).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `e36bdf4c-bef7-4d73-a5ea-e4c11ac8f88a_submission_2026-07-16T14_33_33.239Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
