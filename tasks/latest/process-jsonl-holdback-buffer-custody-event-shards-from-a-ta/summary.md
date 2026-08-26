# Process JSONL holdback-buffer custody event shards from a task directory into st

- **UUID:** `8db1f7d6-57e1-48cf-9f67-e9d081d5a4b2`
- **Slug:** `process-jsonl-holdback-buffer-custody-event-shards-from-a-ta`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Process JSONL holdback-buffer custody event shards from a task directory into structured JSON and CSV reports. Given a task root, load buffer configuration, discover lowercase `.jsonl` shards, replay buffer operations (`INGEST`, `HOLDBACK`, `DISPATCH`, `COMMIT`, `RELEASE`, `TRANSFER`, `PAUSE`, `UNPAUSE`) in contract order, and emit outputs under `/app/output/`.

Normative discovery, reject precedence, duplicate suppression, per-lane ledger semantics, paused scope, executable path, source modules under `/app/replay_tool_src/src/` (`amount.rs`, `apply.rs`, `main.rs`, `output.rs`, `parse.rs`, `precedence.rs`, `reject.rs`, `replay.rs`, `types.rs`), and output formatting are in `/app/task_file/schema.md` and `/app/docs/holdback_buffer_replay_contract.md`. Do not edit contract files or mutate input task trees.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
