# We've got a SIEM custody attestation stack under /app that is supposed to crypto

Submission: `2521620b-0f89-41c8-99c7-090fe2302926`  
Slug: `we-ve-got-a-siem-custody-attestation-stack-under-app-that-is`  
Latest archive: `2521620b-0f89-41c8-99c7-090fe2302926_submission_2026-07-19T09_51_59.380Z.zip`  
Revisions: 4

## Task summary

We've got a SIEM custody attestation stack under /app that is supposed to cryptographically authenticate incident evidence and reject forged or skewed timelines against the signed anti-tamper budgets. In practice operators are seeing witness-MAC seal drift, custody-head breaks across pack order, and rotate-policy epoch mismatches, so hostile packs can still look intact when they are not. Can you restore anti-tamper conformance in /app/chronctl and then emit /app/output/timeline_report.json from /app/data/scenarios.json? The report shape follows /app/docs/report_layout.json and /app/pkg/api/types.go: top-level schema_version, a scenarios array in pack order, and per-row name, finish, active_session_epoch, events_replayed, chain_intact, order_drift_count, contradiction_count, witness_ok_count, and timeline_head_hex. Every row must finish in the state named by /app/config/grading_contract.yaml with domain-correct custody counters and hex heads, and the pack must meet that contract's pack-count and total-event floors. Defaults keep chain_required enabled under /app/config/defaults.yaml. Rotate bands live in /app/config/rotate_schedule.json. Wire rules for zone mapping, custody merges, forensic ties, local seals, and pack-prefix head binding are in /app/docs/wire_format.md.

Required artifacts include: `/app/chronctl`, `/app/output/timeline_report.json`, `/app/data/scenarios.json?`, `/app/docs/report_layout.json`, `/app/pkg/api/types.go`, `/app/config/grading_contract.yaml`, `/app/config/defaults.yaml`, `/app/config/rotate_schedule.json`.

Author anonymous tagged this **medium** security task (tamper-evident, witness-mac, chain-of-custody, anti-tamper, integrity-attestation).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `2521620b-0f89-41c8-99c7-090fe2302926_submission_2026-07-19T09_51_59.380Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
