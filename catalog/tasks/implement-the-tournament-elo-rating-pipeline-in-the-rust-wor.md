# Implement the tournament Elo rating pipeline in the Rust workspace under /app/en

Submission: `c4f0d4fb-bc74-40cd-af5e-aabbadf7a298`  
Slug: `implement-the-tournament-elo-rating-pipeline-in-the-rust-wor`  
Latest archive: `c4f0d4fb-bc74-40cd-af5e-aabbadf7a298_submission_2026-07-10T08_41_52.505Z.zip`  
Revisions in Dropbox: 4

## Task summary

Implement the tournament Elo rating pipeline in the Rust workspace under /app/environment so elo_verify emits a contract-compliant JSON report from the bundled match trace. Read /app/docs/contract.md for the output schema, /app/docs/pipeline_stages.md for stage responsibilities and workspace paths, and /app/docs/elo_formula.md for rating math and aggregate fields. Do not modify sources under /app/environment/tools/elo_verify/ or /app/environment/traces/. The verifier writes the report to the output path specified on its command line; tests consume /tmp/test_report.json.

Required artifacts include: `/app/environment`, `/app/docs/contract.md`, `/app/docs/pipeline_stages.md`, `/app/docs/elo_formula.md`, `/app/environment/tools/elo_verify/`, `/app/environment/traces/`.

Author anonymous tagged this **hard** data-processing task (elo-rating, tournament, ranking-system).

Time estimates: expert ~360 min, junior ~840 min.

Harbor timeouts: agent 900s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `c4f0d4fb-bc74-40cd-af5e-aabbadf7a298_submission_2026-07-10T08_41_52.505Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
