# Ingest recovery report contract

`/app/ingest_recovery_report.json` is produced by the offline stream bench and must contain:

- `scenarios` — one result object per workload scenario id in `/app/environment/data/workloads.json`
- `recovery_digest` — 64-character lowercase sha256 hex over the digest rule below

Each workload scenario in `/app/environment/data/workloads.json` provides:

| field | type | meaning |
|-------|------|---------|
| `scenario_id` | string | scenario label |
| `partitions` | int | lane count for the scenario |
| `members` | int | member slot count for the scenario |
| `records_per_partition` | int | seeded records per lane |
| `max_poll_records` | int | per-poll record ceiling |
| `min_fetch_bytes` | int | minimum fetch byte hint passed into collection |
| `commit_interval_records` | int | target mark cadence in records |

The workload file also defines shared `tick_budget` (int): maximum coordinator ticks any scenario may consume.

Each scenario result includes:

| field | type | meaning |
|-------|------|---------|
| `scenario_id` | string | workload id |
| `records_processed` | int | records consumed before the scenario finished or hit the tick budget |
| `ticks_elapsed` | int | coordinator ticks used |
| `final_residual_records` | int | unconsumed records summed across lanes when the scenario ends |
| `peak_tick_residual` | int | maximum residual backlog observed at any tick during the scenario |
| `throughput_records_per_sec` | number | `records_processed / (ticks_elapsed * 0.01)` rounded to two decimals |
| `commits_per_1000_records` | number | `(commit_count / records_processed) * 1000` rounded to two decimals |
| `assignment_spread` | int | max minus min lane count across member slots |
| `member_loads` | int[] | lane counts per member slot in registry order |
| `idle_member_count` | int | member slots with zero assigned lanes |
| `placement_signature` | int | `sum((i + 1) * member_loads[i])` over member indices `i` |

Healthy recovery for every scenario in the workload file:

- `records_processed` equals `partitions * records_per_partition` for that scenario
- `final_residual_records` is `0`
- `idle_member_count` is `0`
- `assignment_spread` is at most `1`
- `member_loads` sums to `partitions` and each entry differs from the others by at most one lane
- `placement_signature` equals `sum((i + 1) * member_loads[i])` over member indices `i`
- `commits_per_1000_records` satisfies `abs(commits_per_1000_records - (1000 / commit_interval_records)) ≤ 0.15` after rounding the target `1000 / commit_interval_records` to two decimals, and never exceeds `2.0`
- `throughput_records_per_sec` is at least `0.80 * partitions * max_poll_records / 0.01` (equivalently `80 * partitions * max_poll_records`)
- `ticks_elapsed` is strictly less than the shared `tick_budget` and at most `ceil(records_processed / (partitions * max_poll_records)) * 2`

`recovery_digest` concatenates scenario rows sorted by `scenario_id` ascending. For each row append `scenario_id`, `:`, `records_processed`, `:`, `final_residual_records`, `:`, `peak_tick_residual`, `:`, `commits_per_1000_records` formatted with two decimal places, `:`, `assignment_spread`, `:`, `idle_member_count`, `:`, `placement_signature`, with no separators between rows. Hash the UTF-8 bytes with sha256 and emit lowercase hex (same as `python3 /app/environment/tools/check_digest.py` on that string).

Verification helpers under `/app/environment/tools/` are read-only for agents. Tests call `python3 /app/environment/tools/check_digest.py <text>` with a raw UTF-8 string argument.

Cluster metadata in `/app/environment/configs/cluster.json` is loaded by stream-bench and mapped into a runtime profile used while polling, collecting, marking, and placing lanes. Operator notes may disagree with how those fields are honored in the Go tree.

## Verification

Reproduce / regenerate:

```
cd /app/environment && go run /app/environment/cmd/stream-bench --workloads /app/environment/data/workloads.json --cluster /app/environment/configs/cluster.json --report /app/ingest_recovery_report.json
```

The verifier deletes any prior report and reruns that command against the current Go tree under `/app/environment`. Hand-written JSON and edits to workload inputs are not accepted.
