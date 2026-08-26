# We're pulling the adult-nonfiction net-checkout numbers for the fiscal-year-2024

Submission: `ff25c80b-a675-4f9b-a4fa-01582c74f997`  
Slug: `we-re-pulling-the-adult-nonfiction-net-checkout-numbers-for`  
Latest archive: `ff25c80b-a675-4f9b-a4fa-01582c74f997_submission_2026-07-04T07_57_23.788Z.zip`  
Revisions: 1

## Task summary

We're pulling the adult-nonfiction net-checkout numbers for the fiscal-year-2024 board report and need them broken down by branch. The consortium's operational data lake is at /app/data: the per-event circulation log, the item catalog, branches, patrons, holds, fines, and a lot of other operational exports. Some of these describe circulation in more than one way or are summaries, so part of the work is figuring out which exports actually answer the question and reconciling them into one consistent figure. /app/docs/codebook.md is the data dictionary and /app/docs/question.md lists the exact output fields. Fiscal year 2024 runs 2024-07-01 through 2025-06-30 on the consortium's local America/Chicago calendar. A net checkout is a genuine checkout, not a renewal, a return, or a filled hold. The adult-nonfiction collection is the set of items whose item type maps to ADULT_NONFICTION.

Required artifacts include: `/app/data`, `/app/docs/codebook.md`, `/app/docs/question.md`, `/app/analysis.R`, `/app/answer.json`, `/app/R/io_helpers.R`.

Author anonymous tagged this **hard** data-processing task (data-lake, timezone-handling, deduplication, data-reconciliation, fixed-width-parsing, source-of-record, r).

Time estimates: expert ~110 min, junior ~270 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `ff25c80b-a675-4f9b-a4fa-01582c74f997_submission_2026-07-04T07_57_23.788Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
