# schedule_audit.json schema

The coordinator writes a JSON object with:

- `config_id`, `seed`, `profile`, `graph_id`, `run_mode`, `boundary_tick`, `tick_horizon`, `node_count`, `partition_count`
- `flags`: `strict_deps`, `partition_trace` (booleans)
- `jobs`: sorted by `job_id`
- `summary`: aggregate scheduling metrics
- `ticks`: per-tick snapshots
- `partition_ledger`: sorted partition lease rows

`run_mode` is `steady` (default), `checkpoint_resume`, or `checkpoint_chain`. `boundary_tick` is the resume boundary when checkpointing. `boundary_ticks` is an ascending list of boundaries for `checkpoint_chain`.

Each partition ledger row:

- `partition_id` (int)
- `writer_job` (string): empty when no exclusive writer holds the partition
- `publish_tick`, `visible_tick` (ints; `-1` when never published)

Each job row:

- `job_id` (string)
- `start_tick`, `finish_tick`, `queue_wait_ticks`, `duration_ticks`, `node_id` (ints; `-1` means not started/finished/unassigned)
- `duration_ticks` mirrors the fixture duration

Summary:

- `jobs_submitted`, `jobs_completed` (ints)
- `schedule_duration_ticks` (int): max `finish_tick` among completed jobs
- `node_utilization` (float): peak fraction of nodes busy in any single tick (`running_count / node_count`)
- `queue_wait_p95` (int): 95th percentile of positive `queue_wait_ticks` values, computed with index `(n*95+99)/100` on sorted waits (0-based)
- `stall_index` (float): `0` when the final tick has `queued_count == 0`; otherwise `idle_nodes / (queued_count + 1)` from the final tick snapshot
- `schedule_fingerprint` (string): 64-character lowercase SHA-256 hex digest over sorted `job_id|start_tick|finish_tick|queue_wait_ticks` lines (see digest format below)
- `tick_dispatch_digest` (string): SHA-256 hex digest over tick rows formatted `tick|running_count|ready_count|blocked_on_partition|idle_nodes`, LF-joined without trailing newline
- `ledger_fingerprint` (string): SHA-256 hex digest over partition rows formatted `partition_id|writer_job|publish_tick|visible_tick`, LF-joined without trailing newline
- `resume_tick_count` (int): ticks simulated after checkpoint restores (`0` for `steady`; `tick_horizon - boundary_tick` for `checkpoint_resume`; sum of `tick_horizon - b` over each normalized boundary `b` in `boundary_ticks` for `checkpoint_chain`)

Tick row:

- `tick`, `ready_count`, `queued_count`, `running_count`, `idle_nodes`, `blocked_on_partition`

## `schedule_fingerprint` digest format

Recompute with `sha256sum` (or equivalent `hashlib.sha256`) over UTF-8 bytes:

1. Sort `jobs` ascending by `job_id`.
2. For each row, emit one line `job_id|start_tick|finish_tick|queue_wait_ticks` (pipe-separated, decimal integers).
3. Join the lines with a single LF (`\n`) between lines. Do **not** append a trailing newline after the last line.
4. Hash the resulting byte string with SHA-256 and encode as lowercase hexadecimal (64 characters).

Example for two jobs:

```text
root|0|3|0
merge|6|9|0
```

The digest input is the UTF-8 bytes `root|0|3|0\nmerge|6|9|0` (one `\n`, no final `\n`).

## `tick_dispatch_digest` format

1. Walk `ticks` in ascending `tick` order.
2. Emit `tick|running_count|ready_count|blocked_on_partition|idle_nodes` per row.
3. LF-join without trailing newline; SHA-256 lowercase hex.

## `ledger_fingerprint` format

1. Walk `partition_ledger` in ascending `partition_id` order (fixture order).
2. Emit `partition_id|writer_job|publish_tick|visible_tick` per row (`writer_job` empty string when unset).
3. LF-join without trailing newline; SHA-256 lowercase hex.

## Checkpoint lane state

When `run_mode` is `checkpoint_resume`, the runner also writes `/app/output/scheduler_lane_state.json`:

- `config_id`, `seed`, `run_mode`, `boundary_tick`, `schedule_fingerprint`
- `seal_digest`: 64-character lowercase SHA-256 hex over LF-joined lines `config_id`, decimal `seed`, `run_mode`, decimal `boundary_tick`, `schedule_fingerprint`
- `poison_accepted` (bool): always `false` on a correct run; foreign lane files must not change audit output

## Global invariants

- `jobs` is sorted ascending by `job_id`.
- `ticks` has length `tick_horizon` with `tick` values `0 .. tick_horizon - 1` in order; enumerate index equals each row's `tick`.
- The final tick snapshot is the row whose `tick` equals `tick_horizon - 1`.
- `jobs_completed` never exceeds `jobs_submitted`.
- `summary.queue_wait_p95` equals the documented percentile recomputed from positive `queue_wait_ticks` in `jobs`.
- `summary.schedule_duration_ticks` equals the maximum `finish_tick` among completed jobs.
- `summary.node_utilization` equals the peak `running_count / node_count` ratio observed in `ticks`.
- `summary.stall_index` equals `0` when the final tick has `queued_count == 0`; otherwise `idle_nodes / (queued_count + 1)` from the final tick snapshot.
- `summary.schedule_fingerprint` equals the SHA-256 digest over sorted `job_id|start_tick|finish_tick|queue_wait_ticks` lines using the digest format below.
- `summary.tick_dispatch_digest` and `summary.ledger_fingerprint` match the documented digest formats.
- `summary.resume_tick_count` is `0` for `steady` and `tick_horizon - boundary_tick` for `checkpoint_resume`.
- For `checkpoint_resume`, prefix tick snapshots through `boundary_tick - 1` must match a `steady` run with the same profile and seed; full job rows, ticks, ledger, and all three digests must match.
- For `checkpoint_chain`, prefix tick snapshots through each normalized boundary minus one must match the corresponding prefix of a `steady` run; full job rows, ticks, ledger, and all three digests must match the steady run.
- When `strict_deps` is true, every dependency edge requires `parent.finish_tick < child.start_tick` (strict inequality).
- When `strict_deps` is true, a published partition becomes readable on `visible_tick = publish_tick + 1`; when false, `visible_tick = publish_tick`.
- For every started job, `queue_wait_ticks` is non-negative and reflects `start_tick` minus the ready stamp.
- For every completed job, `finish_tick >= start_tick >= 0`.
- Every tick snapshot obeys `running_count <= node_count`, `idle_nodes + running_count == node_count`, and non-negative counters.
- When `ready_count >= 2` while `idle_nodes >= 2`, dispatch must increase `running_count` on that tick rather than leaving nodes idle.
- While jobs remain incomplete, no tick may show `blocked_on_partition >= 1` together with `idle_nodes >= 2`.
- When `ready_count >= 2`, `idle_nodes >= 2`, and `blocked_on_partition == 0`, `running_count` must be at least 2.
- Each job row `duration_ticks` mirrors the fixture `duration` for the same `job_id`.
- Completed jobs must have `start_tick >= 0`, `finish_tick >= start_tick`, and `node_id >= 0`.
- Consumers must not start before every required input partition has `visible_tick >= 0` and `start_tick >= visible_tick`.
- Report `flags` mirror the profile JSON booleans.
- Repeated runs with the same profile must produce identical `schedule_fingerprint`, `tick_dispatch_digest`, `ledger_fingerprint`, and per-job timing fields.
- Completed producers must leave input partitions readable: for every job with inputs, `start_tick >= visible_tick` of each required partition.

## Linear smoke control

On `profiles/linear_smoke.json`:

- `jobs_submitted == 3` and `jobs_completed == 3`.
- `schedule_duration_ticks <= 12`.
- `queue_wait_p95 == 0`.
- `step_a` finishes before `step_b` starts; `step_b` finishes before `step_c` starts (strict: `finish_tick < start_tick` on each edge).

## Diamond mesh expectations

On `profiles/diamond_mesh.json` with `strict_deps` enabled:

- `jobs_submitted` equals the job count in `/app/environment/fixtures/diamond_mesh.json` (four jobs).
- `jobs_completed == jobs_submitted`.
- `queue_wait_p95 == 0`.
- `node_utilization >= 0.5`.
- `schedule_duration_ticks <= 12`.
- `root` finishes before each branch starts; `merge` starts after both branches finish (strict tick gaps on every dependency edge).
- `left` and `right` share the same `start_tick`; both start on the branch burst tick.
- On the first branch `start_tick`, `running_count >= 2`.
- Job `merge` must finish (`finish_tick >= 0`).

## Gradual mesh expectations

On `profiles/gradual_mesh.json`:

- All four jobs complete (`jobs_completed == jobs_submitted`).
- `schedule_duration_ticks <= 12`.
- `queue_wait_p95 == 0`.
- `merge` finishes with `finish_tick >= 0`.
- Each job `start_tick >= submit_tick` from `/app/environment/fixtures/gradual_mesh.json`.
- The final tick snapshot (where `tick == tick_horizon - 1`) has `blocked_on_partition == 0`.

## Fan-in profile

On `profiles/fan_in.json`:

- All six jobs complete.
- `node_utilization == 1.0`.
- `schedule_duration_ticks <= 10`.
- `arm_a`, `arm_b`, `arm_c`, and `arm_d` share the same `start_tick` after `root` completes.
- On the first arm start tick, `running_count == node_count` and `idle_nodes == 0`.
- `bundle` starts after every arm finishes and completes with `queue_wait_ticks == 0`.

## Cascade wave profile

On `profiles/cascade_wave.json`:

- All eight jobs in `/app/environment/fixtures/cascade_wave.json` complete.
- `schedule_duration_ticks <= 24`.
- `queue_wait_p95 == 0`.
- `wave0_a` and `wave0_b` share the same `start_tick`.
- Every dependency edge obeys strict `finish_tick < start_tick`.
- `wave2_finale` finishes with `finish_tick >= 0`.
- Recommended `checkpoint_chain` boundaries: `[5, 11, 17]`.

## Partition ledger

When `partition_trace` is true, every completed producer row in `partition_ledger` for its `output_part` must have `writer_job == ""` and `visible_tick >= 0`.

Lookups for dispatch at tick `T` require `visible_tick <= T` and no exclusive writer on the partition.
