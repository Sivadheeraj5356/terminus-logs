# You took over a catalog-driven query plan simulator that replays scenario tapes 

Submission: `92196d45-f956-4651-8d6e-e137df143ad5`  
Slug: `you-took-over-a-catalog-driven-query-plan-simulator-that-rep`  
Latest archive: `92196d45-f956-4651-8d6e-e137df143ad5_submission_2026-07-10T14_49_13.822Z.zip`  
Revisions: 1

## Task summary

You took over a catalog-driven query plan simulator that replays scenario tapes and writes a plan audit report. Uninterrupted scenarios look fine, but legs that pause and resume often drift from their continuous partners. Join methods change, access paths flip, catalog generations disagree, and plan digests stop lining up even when the summary block still looks calm. Rebuild through /app/ci/build_and_load.sh and emit /app/output/plan_audit.json so every manifest scenario matches the independent tape replay the verifier derives from the bundled tapes. The report must follow /app/doc/plan_audit_contract.txt for schema_anchor, per-row fields (scenario_id, mode, step_alpha_id, step_beta_id, step_gamma_id, stats_gen, stats_ok, pair_ok, plan_digest, finish_reason), and summary counters (scenario_count, scenario_rows, pair_mismatch_count, step_mismatch_total). Copy schema_anchor from /app/stubs/schema_anchor.txt. Tape grammar is in /app/doc/semantics.txt and parity field names are in /app/stubs/replay_contract.txt.

Required artifacts include: `/app/ci/build_and_load.sh`, `/app/output/plan_audit.json`, `/app/doc/plan_audit_contract.txt`, `/app/stubs/schema_anchor.txt`, `/app/doc/semantics.txt`, `/app/stubs/replay_contract.txt`, `/app/cfg/runtime.toml`, `/app/doc/input_checksums.txt`.

Author anonymous tagged this **hard** data-processing task (catalog-replay, query-planner, checkpoint, statistics, c).

Time estimates: expert ~150 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `92196d45-f956-4651-8d6e-e137df143ad5_submission_2026-07-10T14_49_13.822Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
