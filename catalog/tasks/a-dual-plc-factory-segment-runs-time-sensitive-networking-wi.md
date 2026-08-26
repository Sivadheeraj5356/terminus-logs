# A dual-PLC factory segment runs Time-Sensitive Networking with scheduled gate co

Submission: `51fbf555-d1d9-40db-b47b-1d8a4770784d`  
Slug: `a-dual-plc-factory-segment-runs-time-sensitive-networking-wi`  
Latest archive: `51fbf555-d1d9-40db-b47b-1d8a4770784d_submission_2026-07-08T05_51_24.154Z.zip`  
Revisions in Dropbox: 1

## Task summary

A dual-PLC factory segment runs Time-Sensitive Networking with scheduled gate control across three switches, a redundant cross-link, and asymmetric bottlenecks under maintenance derating. Topology, gate schedules, traffic classes, periodic message flows, clock synchronization offsets, packet traces, and the TSN profile overview live under `/app/data/`. Behavioral rules — WCET composition, compliance deadlines derived from traffic-class shaving in `traffic_classes.json`, queue guard bands on gate schedules, bandwidth reservation with per-flow overhead bytes, switch-only clock-skew accumulation with trace jitter, trace miss deduplication when clock skew supersedes observed misses, scheduling-exempt flows, gate-window conflicts, priority-inversion detection, trace validation filtering, metric formulas, and output schemas — are defined in `/app/data/validation_policy.json`. When the overview in `tsn_profile.json` disagrees with the policy or bundled inputs, follow the policy. Build `/app/solution/solve.sh` to read those inputs and write four deterministic artifacts under `/app/output/`: `schedule_validation_report.md`, `deadline_misses.json`, `gate_conflicts.json`, and `network_utilization.csv`. Identical inputs must yield identical outputs on every run. Each output artifact's `sort` field in `validation_policy.json` defines final array ordering (for deadline misses, rank `miss_type` by `miss_type_output_order`, not alphabetically). Assign `conflict_id` values only after sorting gate conflicts per policy; coerce trace timestamps to float before latency rounding; follow...

Required artifacts include: `/app/data/`, `/app/data/validation_policy.json`, `/app/solution/solve.sh`, `/app/output/`.

Author anonymous tagged this **hard** system-administration task (tsn, industrial-networking, real-time, gate-scheduling, deadline-analysis, bandwidth).

Time estimates: expert ~480 min, junior ~1800 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `51fbf555-d1d9-40db-b47b-1d8a4770784d_submission_2026-07-08T05_51_24.154Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
