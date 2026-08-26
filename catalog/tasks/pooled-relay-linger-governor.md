# # Pooled relay linger governor

Submission: `1f6fc6bf-8f01-4913-a4f6-de272f5a4102`  
Slug: `pooled-relay-linger-governor`  
Latest archive: `1f6fc6bf-8f01-4913-a4f6-de272f5a4102_submission_2026-07-09T13_49_32.923Z.zip`  
Revisions: 2

## Task summary

Operations is shipping the Rust edge relay coordinator under `/app/environment` for offline shard polling. Bundled smoke workloads finish, but larger profiles either abort with descriptor pressure or leave idle pooled sockets unreclaimed after mock shards close quiet connections. Complete the coordinator by fixing Rust source under `/app/environment` so pooled transport reuse, linger governance, and export reconciliation match the contract. Library behavior in the workspace crates must match the contract, not only the CLI layer. Rebuild using the operator runbook cargo invocation; the verifier rebuilds and reruns `/app/bin/relayctl run`. Manual or hand-written exports are insufficient; the normal pipeline must regenerate `/output/relay_run_report.json`, `/output/pool_journal.csv`, and `/output/relay_trace.ndjson`.

Required artifacts include: `/app/environment`, `/app/bin/relayctl`, `/output/relay_run_report.json`, `/output/pool_journal.csv`, `/output/relay_trace.ndjson`, `/app/docs/operator_runbook.md`, `/app/docs/run_report_schema.md`, `/app/docs/journal_schema.md`.

Author anonymous tagged this **hard** system-administration task (relay, tcp-pool, linger, descriptor-budget, rust).

Time estimates: expert ~150 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `1f6fc6bf-8f01-4913-a4f6-de272f5a4102_submission_2026-07-09T13_49_32.923Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
