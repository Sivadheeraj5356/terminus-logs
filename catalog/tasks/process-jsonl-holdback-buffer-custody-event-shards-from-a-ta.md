# Process JSONL holdback-buffer custody event shards from a task directory into st

Submission: `8db1f7d6-57e1-48cf-9f67-e9d081d5a4b2`  
Slug: `process-jsonl-holdback-buffer-custody-event-shards-from-a-ta`  
Latest archive: `8db1f7d6-57e1-48cf-9f67-e9d081d5a4b2_submission_2026-07-19T12_14_09.104Z.zip`  
Revisions in Dropbox: 1

## Task summary

Process JSONL holdback-buffer custody event shards from a task directory into structured JSON and CSV reports. Given a task root, load buffer configuration, discover lowercase `.jsonl` shards, replay buffer operations (`INGEST`, `HOLDBACK`, `DISPATCH`, `COMMIT`, `RELEASE`, `TRANSFER`, `PAUSE`, `UNPAUSE`) in contract order, and emit outputs under `/app/output/`. Normative discovery, reject precedence, duplicate suppression, per-lane ledger semantics, paused scope, executable path, source modules under `/app/replay_tool_src/src/` (`amount.rs`, `apply.rs`, `main.rs`, `output.rs`, `parse.rs`, `precedence.rs`, `reject.rs`, `replay.rs`, `types.rs`), and output formatting are in `/app/task_file/schema.md` and `/app/docs/holdback_buffer_replay_contract.md`. Do not edit contract files or mutate input task trees. Keep those modules separate; do not collapse them into one file. Run the installed holdback processor with exactly one `<task_root>` directory argument (for example `/app/task_file` or a copy under `/tmp/`). Wrong arity or a non-directory root is fatal before `/app/output/` is touched: silent nonzero exit, empty stdout and stderr, preserve existing `/app/output/` bytes. Success deletes and recreates `/app/output/` quietly, exits zero with empty stdout and stderr, and leaves the task tree unchanged. Load and validate config and events before deleting `/app/output/` on success.

Required artifacts include: `/app/output/`, `/app/replay_tool_src/src/`, `/app/task_file/schema.md`, `/app/docs/holdback_buffer_replay_contract.md`, `/app/task_file`, `/app/output/result.json`, `/app/output/audit.csv`, `/app/output/rejects.csv`.

Author anonymous tagged this **hard** data-processing task (holdback-buffer, jsonl-replay, lane-ledger, per-lane-slices, buffer-custody, state-machine).

Time estimates: expert ~180 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `8db1f7d6-57e1-48cf-9f67-e9d081d5a4b2_submission_2026-07-19T12_14_09.104Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
