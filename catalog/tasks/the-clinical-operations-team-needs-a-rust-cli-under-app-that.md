# The clinical operations team needs a Rust CLI under `/app` that rebuilds hospita

Submission: `67c458ba-2129-47c1-aa33-9f3c39c48140`  
Slug: `the-clinical-operations-team-needs-a-rust-cli-under-app-that`  
Latest archive: `67c458ba-2129-47c1-aa33-9f3c39c48140_submission_2026-07-05T19_47_04.113Z.zip`  
Revisions in Dropbox: 1

## Task summary

The clinical operations team needs a Rust CLI under `/app` that rebuilds hospital census and procedure analytics from CSV event feeds. Build and run: ```bash cd /app && cargo build --release --locked cd /app && ./target/release/hospital_analytics --input-dir /app/data --output /app/output/analytics_report.json ```

Required artifacts include: `/app/data`, `/app/output/analytics_report.json`, `/app/docs/`, `/app/data/README.md`.

Author anonymous tagged this **hard** data-processing task (rust, csv, json, healthcare, analytics).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `67c458ba-2129-47c1-aa33-9f3c39c48140_submission_2026-07-05T19_47_04.113Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
