# Export artifacts

Replay exports land under `/app/output` by default.

## trim_transcript.json

Object with `rows[]`:

- `peer_id` (string)
- `span_start` (integer)
- `span_end` (integer)
- `stride_units` (integer)
- `lane_tick` (integer)

After a multi-window replay completes, `rows[]` represents the active replay
window only. Earlier completed windows remain reflected through checkpoint,
staging, digest, and trace ceilings; they are not replayed as cumulative
transcript rows.

## slot_map_digest.json

Object with `views[]`:

- `peer_id` (string)
- `body_hex` (string, sixteen lowercase hex characters)
- `epoch` (integer)
- `lane_tick` (integer)
- `series_num` (integer)
- `series_den` (integer)
- `slots_free` (integer)
- `applied_bytes` (integer)
- `skipped_bytes` (integer)

`body_hex` is the first sixteen hex characters of SHA-256 over the first eight bytes of `/app/environment/data/seed_extents.bin` followed by one byte holding `epoch` as unsigned 8-bit.

Each replay window uses a single ordinal ladder for transcript `lane_tick`,
trace `tick`, and digest `epoch`. Within one window those ticks strictly
increase in peer export order. When a later window starts, its first tick must
be above the prior window ceilings already visible in the transcript tail,
propagation trace, digest epoch, checkpoint/staging markers, and the current
volume fixture tick.

When export overlay keeps `export_epoch_from_transcript_tail`, digest `epoch`
is the highest `lane_tick` across the active transcript window (the last peer
row once ticks increase in export order). It is not the first peer's
`lane_tick`.

`series_num` / `series_den` follow the bind-policy profile chain: read
`active_profile` from `/app/environment/config/bind_policy.toml`, resolve that
profile's `num_field` / `den_field` in
`/app/environment/config/series_profiles.toml`, then take those field values
from `/app/environment/config/volume.toml`. Do not substitute the util-ratio
fixture pair when series source is the profile chain.

`slots_free` on each digest view follows the volume slot inventory for the
active replay window (volume fixture `slots_free`), not the array-side cleared
count.

At convergence each digest view reports `skipped_bytes` of 0 while
`applied_bytes` remains positive. The final convergence cycle still reports
`applied_bytes` greater than `skipped_bytes`.

## propagation_trace.jsonl

One JSON object per line:

- `tick` (integer)
- `a_val` (integer)
- `b_val` (integer)

Trace metric names come from `/app/environment/fixtures/trace_binding.toml`.
When `trace_array_metric` is `cleared_ordinal`, `a_val` is the array fixture
`cleared_units` for the active window — not the span byte offset
(`span_start`). When `trace_volume_b_metric` is `lane_tick`, `b_val` equals the
row's lane tick (same ordinal as `tick`), not a span quotient.

## convergence_report.json

Object with `cycles[]`:

- `cycle` (integer)
- `applied_bytes` (integer)
- `skipped_bytes` (integer)

## Persistence markers

- `/app/environment/data/checkpoint.seq` — integer text file
- `/app/environment/data/staging.rev` — integer text file
- `/app/environment/data/window.phase` — two bytes: completed replay-window count, then completed window ordinal

`checkpoint.seq` and `staging.rev` store the converged digest epoch after a
successful export. `window.phase` is separate from the epoch ladder: after a
two-window convergence both bytes are `2`, even when the digest epoch is higher
than `2`.
