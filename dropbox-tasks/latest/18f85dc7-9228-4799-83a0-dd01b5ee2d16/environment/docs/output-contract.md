# Compile output contract

## Commands

```bash
node /app/environment/cli/driver.mjs compile --spec /app/environment/specs/operator.json --out /app/output
node /app/environment/cli/driver.mjs cache-reset
node /app/environment/cli/driver.mjs status --trace /app/output/pass.trace.json
```

`compile` writes `kernel.mjs`, `pass.trace.json`, and `metrics.json` under the output directory and maintains build cache under `/app/output/.cache/`. After `cache-reset`, the next compile must clear stale cache entries and reconstruct all state.

## Operator spec

`/app/environment/specs/operator.json` defines `ghost_width`, `tolerance.epsilon`, and a `packs` array. Each pack entry binds a grid fixture, tile shape, spill budget, and edge predication threshold. The three packs (`alpha`, `beta`, `gamma`) are processed sequentially during each compile.

`ghost_width` counts the halo cells added on each side of a grid before divisor and lane-width selection.

## Padded extents and divisors

For each pack, form padded extents by adding `2 * ghost_width` to `nx`, `ny`, and `nz` from that pack grid fixture. The `divisors` field in the trace record lists every positive integer that divides all three padded extents, sorted ascending. The chosen `lane_width` must be one of those shared divisors.

## Trace schema

`/app/output/pass.trace.json` contains a `records` array with one entry per pack in spec order. Each record exposes `pack_id`, `spill_total`, `scratch_peak`, `edge_mode`, `lane_width`, and the full `divisors` list.

`edge_mode` is `duplicate` when that pack grid `boundary_fraction` is strictly greater than its `predication_cutoff`; otherwise `edge_mode` is `predicated`.

When a pack enables `temporal_tiling`, its `scratch_peak` must stay within that pack `scratch_cap_bytes`.

Each pack `spill_total` must respect that pack `spill_budget`.

Peel spill accounting: `base_spill = floor(tile_volume / lane_width)` where `tile_volume` is the product of the pack tile dimensions. When `edge_mode` is `duplicate`, add `peel_rows * 3` to `base_spill`; when `edge_mode` is `predicated`, add `peel_rows`. `peel_rows` is `ceil(boundary_fraction * max(nx, ny, nz))` from the pack grid fixture.

## Metrics schema

`/app/output/metrics.json` aggregates `spill_total`, `max_scratch_bytes`, `lane_width_summary`, `compile_epoch`, `replay_generation`, `replay_entry_count`, and `digest_chain` (64-character hex digest). `spill_total` equals the sum of per-pack `spill_total` values in the trace. `max_scratch_bytes` equals the maximum `scratch_peak` across records. `lane_width_summary` lists each pack `lane_width` in spec order.

`compile_epoch` is a positive integer run counter persisted under `/app/output/.cache/compile_journal.json`. It starts at `1` on the first successful compile, stays unchanged across incremental recompiles on unchanged inputs, and increments by exactly one after each `cache-reset` followed by a successful compile. Two successive reset-then-compile cycles advance `compile_epoch` by two relative to the epoch before the first reset.

### Migration WAL

Each `cache-reset` followed by a successful compile appends one segment to `/app/output/.cache/wal_segment.json`. Segments are objects `{ seq, prior_epoch, next_epoch }` where `next_epoch` equals `prior_epoch + 1`. When the journal file epoch disagrees with the WAL tail, epoch reconciliation must use the greater of the stored journal epoch and the WAL tail `next_epoch`, persist that reconciled epoch back into the journal and replay log generation field, and emit metrics with the reconciled value. After a successful post-migration compile completes, WAL segments are cleared.

`replay_generation` equals `compile_epoch` and equals the `generation` field stored in `/app/output/.cache/replay_log.json` after every successful compile.

`replay_entry_count` is the number of replay-log entries whose `generation` field equals the current `compile_epoch`. It increases by exactly one for each successful compile in the active generation: the first successful compile in a generation yields `1`, and three successive successful compiles without `cache-reset` yield `3`. `compile_epoch` and `replay_generation` stay unchanged across those incremental compiles. The latest replay-log entry `digest` equals `digest_chain` for that compile, and each entry `packCount` equals the operator spec pack count.

### Replay log

`/app/output/.cache/replay_log.json` stores `{ generation, entries }`. Each entry records `{ generation, packCount, digest, ts }` where `packCount` is the number of packs compiled, `digest` equals the `digest_chain` written for that compile, and `generation` matches the journal epoch active when the entry was recorded.

On `cache-reset` migration, stale replay entries are truncated and `generation` advances in lockstep with `compile_epoch`. Incremental compiles on unchanged inputs must not change `generation` or remove prior entries for the active generation.

### Digest chain and trace tail projection

`digest_chain` binds a projected trace tail and `kernel.mjs` bytes via `/app/environment/lib/canon_json.mjs` and `/app/environment/lib/hash_util.mjs`.

The trace tail is **not** the full final trace record. It is a six-field projection of the last record in `pass.trace.json`, containing exactly these keys in this semantic set:

- `pack_id`
- `spill_total`
- `scratch_peak`
- `edge_mode`
- `lane_width`
- `divisors`

Fields such as `tile` and `peel_rows` belong in the trace record but must be excluded from the tail projection. The digest concatenates `canon_json(projected_tail)` with the UTF-8 `kernel.mjs` source before hashing.

Digest cache entries may be stored under `/app/output/.cache/`. Each cache file is a JSON object with a `data` field holding the payload (for digest entries, `data.digest` and optionally `data.trace_hash`). A cached digest is valid only when it matches the digest recomputed from the projected trace tail and the current `kernel.mjs` bytes, and when its stored `trace_hash` matches the canonical hash of the current trace records. If a digest cache entry is missing, incomplete, corrupted, or bound to a mismatched trace hash, the compile must emit the recomputed digest and must not propagate the stale cache value into `digest_chain`.

### Cache dependency graph

Cache entries may declare a `deps` array naming other cache keys that must be present and readable before reuse. A cache hit is valid only when every named dependency entry exists and is readable. Stage entries that depend on pack or phase outputs must miss when an upstream dependency is absent or invalidated.

Pack tiling and edge metadata are cached under keys prefixed `phase_a:`. Stage-two rows depend on pack keys and phase outputs; removing an upstream `phase_a:` or `pack:` entry must force downstream recomputation rather than reusing stale spill totals.

`cache-reset` migration must evict stage-level cache rows (`stage_two`, `stage_two_raw`, and related prefixes) while preserving journal and replay sidecars until the migration handler rewrites them.

## Replay semantics

Unchanged inputs must produce stable `digest_chain`, `compile_epoch`, `replay_generation`, per-pack spill totals, and trace records across incremental recompiles. `replay_entry_count` is not stable across incremental compiles: each successful compile in the active generation appends one replay-log row and increments `replay_entry_count` by one while `compile_epoch` and `replay_generation` remain fixed until `cache-reset`. After `cache-reset`, a rebuild must match a clean compile, must advance `compile_epoch` by one relative to the epoch observed before the reset, and must reset `replay_entry_count` to `1` on the next successful compile. The replay log records compile entries; migration must truncate stale replay entries and advance generation in lockstep with the journal epoch.

Metrics aggregation must derive from the live trace records in spec order. Cached trace snapshots must not reorder records when computing `lane_width_summary` or `spill_total`. Stage-two cache hits must not re-apply peel accounting to totals that already include peel spill.

The status command reports `register_estimate` as the sum of per-record `spill_total` values from the trace file it reads.

## Kernel numerics

`kernel.mjs` must export `apply(volume, nx, ny, nz)` and return stencil results that match the reference executor in `/app/environment/runtime/ref_exec.mjs` within the relative tolerance declared in the operator spec.
