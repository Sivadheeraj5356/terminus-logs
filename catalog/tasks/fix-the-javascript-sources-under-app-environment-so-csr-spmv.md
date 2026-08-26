# Fix the JavaScript sources under /app/environment so CSR SpMV stays under the no

Submission: `aec3ecd3-10d8-443a-a1e5-7b3507b42c24`  
Slug: `fix-the-javascript-sources-under-app-environment-so-csr-spmv`  
Latest archive: `aec3ecd3-10d8-443a-a1e5-7b3507b42c24_submission_2026-07-17T10_24_29.469Z.zip`  
Revisions: 4

## Task summary

Fix the JavaScript sources under /app/environment so CSR SpMV stays under the nonzero cap in /app/environment/docs/nlim.toml, and residual norms for every pack under /app/environment/suite land inside the absolute and relative bands published there (and in each pack meta.toml). Run this probe command

Required artifacts include: `/app/environment`, `/app/environment/docs/nlim.toml`, `/app/environment/suite`, `/app/environment/tools/drive_a.mjs`, `/app/output/slot_map.json`, `/app/output/band_tbl.json`, `/app/output/run_log.jsonl`, `/app/output`.

Author anonymous tagged this **hard** scientific-computing task (javascript, csr, spmv, sparse-matrix, floating-point, scientific-computing).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 900s, verifier 300s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `aec3ecd3-10d8-443a-a1e5-7b3507b42c24_submission_2026-07-17T10_24_29.469Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
