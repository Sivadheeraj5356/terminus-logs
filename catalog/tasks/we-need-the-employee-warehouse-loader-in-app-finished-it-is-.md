# We need the employee warehouse loader in /app finished. It is a Rust CLI that sh

Submission: `04c4a6cd-c487-4e44-9a73-8705c0c26727`  
Slug: `we-need-the-employee-warehouse-loader-in-app-finished-it-is-`  
Latest archive: `04c4a6cd-c487-4e44-9a73-8705c0c26727_submission_2026-07-06T11_23_46.077Z.zip`  
Revisions in Dropbox: 2

## Task summary

We need the employee warehouse loader in /app finished. It is a Rust CLI that should be run as cargo run -- ingest --db /absolute/path/to/warehouse.sqlite --input /absolute/path/to/feed.csv, and the input can also be a directory of csv files. The feed contract and the SQLite table contract are in /app/docs/source_contract.txt. The business requirement is full Slowly Changing Dimension Type 2 tracking for the employee roster. Loading old batches, replaying the same batch, or receiving late corrections must leave /app with one clean employee_history timeline per employee: no overlapping windows, no duplicate no-change rows, one current row per employee, and corrected records replacing the older record for the same employee and effective date. Bad rows should be rejected without stopping the rest of the file, with enough detail left in employee_rejects for operations to follow up.

Required artifacts include: `/app/docs/source_contract.txt`.

Author anonymous tagged this **hard** data-processing task (sqlite, scd-type-2, csv, rust, reconciliation).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `04c4a6cd-c487-4e44-9a73-8705c0c26727_submission_2026-07-06T11_23_46.077Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
