# Operator notes

The slot list inspector and guest utility share fixture-backed views under
`/app/environment/fixtures`. After a maintenance window, rerun the replay
driver from `/app` and inspect artifacts under `/app/output` before retrying
provisioning.

The list inspector prints `slots_free` from the active array fixture.
The guest utility `try` subcommand validates cross-view alignment in
generated digests before accepting new work.

When a second replay window follows a cleared-units fixture, compare
`propagation_trace.jsonl` against `slot_map_digest.json` and the window marker at
`/app/environment/data/window.phase` before trusting readiness probes or
inventory listings alone.

Dashboard series follow the ratio named in `/app/environment/fixtures/util_ratio.json`.

## Output artifacts

`/app/output/trim_transcript.json` lists submitted span windows per cycle.
Each row names its peer in `peer_id`, span bounds in `span_start` and `span_end`,
stride metadata in `stride_units`, and the lane counter in `lane_tick`.

`/app/output/slot_map_digest.json` carries one view row per peer. The `views[]` rows
include `peer_id`, `body_hex`, `epoch`, `lane_tick`, `series_num`,
`series_den`, `slots_free`, `applied_bytes`, and `skipped_bytes`. After a cleared-units
fixture with positive `cleared_units`, `epoch` and `lane_tick` must agree on every view
when the pipeline has converged. Dashboard series must follow the active ratio
in `/app/environment/fixtures/util_ratio.json`, not raw array cleared counters alone.

`/app/output/propagation_trace.jsonl` records authority disagreements. Each line
carries a `tick` counter plus paired `a_val` and `b_val` counters that stay
positive and non-decreasing. Trace ticks share the digest epoch counter, must
not exceed the digest epoch, and ticks from the second replay window must
exceed every tick from the first window. Within each window, consecutive peer
rows must emit strictly increasing trace ticks. The final trace row
satisfies `trace[-1].tick` equals the converged digest epoch. Each transcript row
`lane_tick` must equal the trace tick on the same ordinal within
the latest replay window.

`/app/output/convergence_report.json` summarizes each replay window. The
`cycles[]` rows report `cycle`, `applied_bytes`, and `skipped_bytes`.

## Body digest

For each peer snapshot, compute a sha256 digest over the canonical byte sequence
formed by the first eight bytes of `/app/environment/data/seed_extents.bin`
followed by one byte holding that row's `views[].epoch` as an unsigned 8-bit
value. Emit the first 16 characters of the lowercase hex digest without a prefix
in `views[].body_hex`. Each `body_hex` value is exactly 16 lowercase hex characters.

## Replay invariants

After two replay windows, the latest convergence row shows positive
applied bytes with valid body hashes per the formula above. The converged digest
epoch must exceed the cleared-units fixture tick when `cleared_units` is positive.
`/app/bin/volutil` rejects new work when exported artifacts show split authority
views even though `/app/bin/listctl` still reports ample array cleared units.
Session listing returns the session value from `/app/environment/config/volume.toml`.

The second replay window must advance the shared epoch counter beyond
the prior-window digest ceiling and the cycle-two volume slot row tick. After
each replay window completes, the window marker's second byte equals that
window ordinal and its coordinator byte equals two. Append reruns for the same
window must not duplicate `trim_transcript` rows or rewind the coordinator
phase byte.
