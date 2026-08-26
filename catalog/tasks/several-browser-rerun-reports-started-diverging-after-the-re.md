# Several browser rerun reports started diverging after the retry-policy cleanup. 

Submission: `21db18f7-045f-42d8-8f80-7fe70f2def24`  
Slug: `several-browser-rerun-reports-started-diverging-after-the-re`  
Latest archive: `21db18f7-045f-42d8-8f80-7fe70f2def24_submission_2026-07-11T13_03_22.507Z.zip`  
Revisions: 2

## Task summary

Several browser rerun reports started diverging after the retry-policy cleanup. Historical flaky-test prioritization has been miscounting failures since the v2.0 schema changes introduced rerun session tracking and soft-deleted rows in the SQLite history database. Before expanding the reproduction tooling further, stabilize historical aggregation so flaky counts reflect only valid original sessions. The flaky-repro CLI under /app reads from /app/db/history.db; see /app/README.md for schema context and /app/docs/output-contracts.md for the report.json layout.

Required artifacts include: `/app/db/history.db`, `/app/README.md`, `/app/docs/output-contracts.md`, `/app/logs/report.json`.

Author anonymous tagged this **hard** debugging task (playwright, sqlite, node, cli, debugging, qa-tooling).

Time estimates: expert ~60 min, junior ~150 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `21db18f7-045f-42d8-8f80-7fe70f2def24_submission_2026-07-11T13_03_22.507Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
