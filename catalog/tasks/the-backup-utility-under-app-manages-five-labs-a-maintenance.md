# The backup utility under `/app` manages five labs. A maintenance window left the

Submission: `d20e9a96-92ec-43d5-8935-b126b122c9c0`  
Slug: `the-backup-utility-under-app-manages-five-labs-a-maintenance`  
Latest archive: `d20e9a96-92ec-43d5-8935-b126b122c9c0_submission_2026-07-15T15_57_04.048Z.zip`  
Revisions: 1

## Task summary

The backup utility under `/app` manages five labs. A maintenance window left the system unable to complete its `fieldday-2026-06-18` restore drill — the tool exits with errors and produces no output. The operational state of the data layer was disrupted by the maintenance. Documentation under `/app/docs/` describes the storage layout and output contracts. The tool source is under `/app/src/`.

Required artifacts include: `/app/docs/`, `/app/src/`, `/app/restore/fieldday-2026-06-18/`, `/app/repair.json`, `/app/docs/repair-contract.md`.

Author anonymous tagged this **hard** system-administration task (backup, deduplication, restore, rust, state-reconciliation).

Time estimates: expert ~60 min, junior ~180 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `d20e9a96-92ec-43d5-8935-b126b122c9c0_submission_2026-07-15T15_57_04.048Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
