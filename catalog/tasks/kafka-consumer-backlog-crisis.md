# # Kafka Consumer Backlog Crisis

Submission: `001ea154-61a1-41ee-a51a-44e8f22786f8`  
Slug: `kafka-consumer-backlog-crisis`  
Latest archive: `001ea154-61a1-41ee-a51a-44e8f22786f8_submission_2026-07-16T08_09_09.227Z.zip`  
Revisions: 3

## Task summary

Order-ingest is tens of thousands of records behind. CPU and memory stay flat, so scale-out is off the table for this shift. The offline recovery bench under `/app/environment` loads cluster metadata, runs workload scenarios, and writes `/app/ingest_recovery_report.json` with `scenarios` and a `recovery_digest` (64-character lowercase hexadecimal). Field meanings, numeric health rules, and how to regenerate the report live in `/app/environment/data/report_contract.md`. Workload shapes and `tick_budget` are in `/app/environment/data/workloads.json`. Operator notes elsewhere under `/app/environment` may disagree with each other or with the cluster file.

Required artifacts include: `/app/environment`, `/app/ingest_recovery_report.json`, `/app/environment/data/report_contract.md`, `/app/environment/data/workloads.json`, `/app/environment/tools/`.

Author anonymous tagged this **hard** system-administration task (kafka, streaming, consumer-groups, throughput, go).

Time estimates: expert ~60 min, junior ~150 min.

Harbor timeouts: agent 1500s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `001ea154-61a1-41ee-a51a-44e8f22786f8_submission_2026-07-16T08_09_09.227Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
