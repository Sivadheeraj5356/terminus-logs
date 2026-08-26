# Contact stability report

Write exactly one file: `/app/results/contact_stability_report.json`.
UTF-8 JSON with a trailing newline. Repeated runs on the same inputs must be byte identical.

## Top level

```
{
  "summary": { ... },
  "scenes": [ ... ]
}
```

Keys are exactly `summary` then `scenes`. No other top level keys.

### JSON key order (normative)

Top level: `summary`, `scenes`.

`summary`: `scenes_analyzed`, `unstable_scenes`, `stable_scenes`, `total_violations`, `stress_replays_run`, `stress_replays_passed`.

Each `scenes[]` element: `scene_id`, `unstable`, `violations`, `max_penetration_m`, `impulse_chain_len`, `stress`.

`stress`: `replays_run`, `replays_passed`, `validated`.

Each `violations[]` element: `kind`, `frame`, `bodies`, `detail`.

## summary

```
{
  "scenes_analyzed": int,
  "unstable_scenes": int,
  "stable_scenes": int,
  "total_violations": int,
  "stress_replays_run": int,
  "stress_replays_passed": int
}
```

`stable_scenes` counts rows with `unstable` false.

## scenes

One object per file `scene_01.json` through `scene_20.json` in the scenarios directory,
sorted by `scene_id` ascending. Ignore other `scene_*.json` files in that directory.

When `unstable` is false, `violations` is `[]` (never null).

### Per-scene metrics

`max_penetration_m` is the maximum `penetration_m` from input contacts across all frames (JSON float, no rounding).

`impulse_chain_len` is the longest same-frame contact chain where each contact's `body_b` equals the next contact's `body_a`. Use `0` when every frame has an empty `contacts` array. Use at least `1` when any frame has contacts (`scene_05` chained case is `2`).

### Frame replay order

Process `frames[]` in JSON array order as stored in the scene file. Do not re-sort frames by the `frame` integer before analysis; consecutive-frame rules (for example `stacking_instability`) refer to adjacent entries in that array.

Before simulating each frame, sort its `contacts` by `contact_policy.yaml` `ordering.primary_key`
(`frame` ascending on the parent frame, then `ordering.secondary_key` `contact_id` ascending).

### Violation detection

Apply `/app/rules/contact_policy.yaml`. Emit violations for:

- `penetration_artifact`: resolved penetration exceeds `resolution.max_penetration_m` plus `resolution.penetration_tolerance_m`
- `stacking_instability`: three consecutive frames with vertical normal (`normal_y` > 0.5) and strictly increasing `penetration_m` on the same body pair
- `impulse_chain_break`: chained contacts in one frame where any `impulse_normal` transfer is below `impulse.chain_min_transfer`
- `friction_drift`: on each contact in each frame, `abs(impulse_tangent)` exceeds `friction.cumulative_drift_threshold_m_s` (per-contact instantaneous check, not summed across frames)
- `restitution_violation`: `restitution` outside `resolution.restitution_clamp_min`..`resolution.restitution_clamp_max` (detail `restitution out of clamp`), or once per unordered body pair when `restitution > 0`, `normal_y > 0.5`, and relative normal separation `(velocities[body_a].y - velocities[body_b].y) * normal_y > 0` using the contact's `body_a`/`body_b` fields as velocity map keys (detail `separating normal velocity with positive restitution`). Approaching contacts (relative normal velocity ≤ 0) do not emit this detail.
- `stale_manifold`: `manifold_id` persists more than `manifolds.max_survival_frames` after contact removal
- `layer_filter_miss`: when `layers.enforce_mask` is true, both contact bodies must be present in `bodies` and both layer masks must exist in `layers`; emit only when those masks do not intersect. If either body is missing from `bodies`, or either layer mask is absent, skip the check (no violation).
- `constraint_violation`: constraint separation exceeds `limit_m` by more than `constraints.max_violation_m`
- `phase_mismatch`: narrowphase pair absent from broadphase when `broadphase.require_narrowphase_subset` is true. Broadphase body order is unordered; `["B","A"]` matches `["A","B"]`.
- `tunneling`: for each body, displacement between its positions in consecutive `frames[]` entries exceeds `tunneling.velocity_threshold_m_s * (tunneling.timestep_ns / 1e9)` (compare using the frames array order, not sorted frame numbers)
- `sleep_activation_error`: sleeping body (`sleeping: true` in `bodies`) with speed `hypot(velocity.x, velocity.y)` above `sleep.activation_velocity_threshold_m_s` using that frame's `velocities` entry

Sort `violations` by `kind`, then `frame`, then comma-joined `bodies`. Deduplicate identical kind, frame, and bodies tuples. Two contacts sharing a `contact_id` but different body pairs are not duplicates.

Each violation rule is evaluated independently. A contact may produce multiple violations in the same frame. `phase_mismatch` must not suppress `penetration_artifact` on another contact in the same frame.

### Violation detail strings (normative)

Use exactly these `detail` values:

| kind | detail |
|------|--------|
| penetration_artifact | `penetration %.4f m` using the contact `penetration_m` |
| stacking_instability | `monotonic penetration growth` |
| impulse_chain_break | `impulse transfer below chain minimum` |
| friction_drift | `tangent impulse exceeds drift threshold` |
| restitution_violation | `restitution out of clamp` or `separating normal velocity with positive restitution` |
| stale_manifold | `manifold survived after contact removal` |
| layer_filter_miss | `layer masks do not intersect` |
| constraint_violation | `separation exceeds limit` |
| phase_mismatch | `narrowphase pair missing from broadphase` |
| tunneling | `displacement exceeds velocity threshold` |
| sleep_activation_error | `sleeping body moving too fast` |

For `stale_manifold`, set `bodies` to `[manifold_id]` (not body ids). Emit once per manifold on the first frame where survival exceeds `manifolds.max_survival_frames`.

For `impulse_chain_break`, set `bodies` to `[first_body_in_chain, last_body_in_chain]` across the broken chain segment.

See **Per-scene metrics** above for `max_penetration_m` and `impulse_chain_len`.

### Layer mask intersection

Layer id `L` uses mask `layers["L"]` as a bitmask. Body on layer `A` may collide with body on layer `B` only when `(mask[A] & (1 << (B-1))) != 0` and `(mask[B] & (1 << (A-1))) != 0`.

### stress

**Default (no schedules):** If the scene JSON has no `stress` object, or `stress.schedules` is missing/empty, use `replays_run` 0, `replays_passed` 0, `validated` true. When `replays_run` is 0, `validated` must be true (never false).

Let `baseCount` be `len(violations)` from the full-scene analysis before stress replay.

For each schedule, build replay frames from `frame_order` by including only frame indices that exist in the scene. Missing indices are skipped during replay but still count in `len(frame_order)` for the span rules below.

A schedule **passes** when analyzing only its replay frames yields `len(replayViolations) <= baseCount`. Re-detecting the same violations as the baseline still passes; only a strict increase in violation count fails the schedule. Example: `scene_13` has one `layer_filter_miss` at baseline; replaying frame `0` alone still finds that violation and counts as passed (`replays_passed` 1).

`replays_run` is the schedule count. `replays_passed` is how many schedules pass. Initially set `validated` to `(replays_passed == replays_run)`.

When the scene is unstable and `baseCount > 0`, optionally override `validated` using the scene's total frame count `F` (number of `frames[]` entries) and each schedule's declared `len(frame_order)` (including indices absent from the scene):

- If **every** schedule has `len(frame_order) < F`, force `validated` true (bundled `scene_10` and `scene_13`).
- If **every** schedule has `len(frame_order) >= F`, force `validated` false (bundled `scene_14`; `truncated_stress` fixture on `scene_13` with `[0, 99]` has declared length 2 >= F=2).
- If schedules are **mixed** (at least one with `len(frame_order) < F` and at least one with `len(frame_order) >= F`), apply **neither** override — keep `validated = (replays_passed == replays_run)`. Example: `mixed_stress_schedules` on `scene_13` with prefix `[0]` and full `[0,1]` stays `validated` true when both schedules pass.

Example (`truncated_stress`): `scene_13` has frames 0 and 1. Schedule `[0, 99]` replays only frame 0 but declared length 2 spans all frames, so `validated` is false even though index 99 is skipped.

When `stress.enforce_impulse_order` is true, sort contacts by `contact_id` within each replayed frame before analysis.

## Bundled verifier expectations

The harness tests your report against unmodified `/app/scenarios/scene_01.json` through
`scene_20.json`. Do not edit bundled inputs; the verifier recomputes each file SHA256.

### Bundled unstable flags for all twenty scenes

| scene_id | unstable |
|----------|----------|
| scene_01 | true |
| scene_02 | false |
| scene_03 | true |
| scene_04 | false |
| scene_05 | true |
| scene_06 | false |
| scene_07 | true |
| scene_08 | false |
| scene_09 | true |
| scene_10 | true |
| scene_11 | true |
| scene_12 | false |
| scene_13 | true |
| scene_14 | true |
| scene_15 | false |
| scene_16 | true |
| scene_17 | false |
| scene_18 | true |
| scene_19 | true |
| scene_20 | false |

Summary on bundled data: `unstable_scenes` 12, `stable_scenes` 8, `total_violations` 13.

Only `scene_10`, `scene_13`, and `scene_14` include `stress.schedules`. Seventeen scenes emit `replays_run` 0.

### Per-scene bundled violation expectations

The verifier checks unstable flags plus the rows below on `/app/scenarios/`.

| scene_id | violations | kinds | impulse_chain_len | stress.validated |
|----------|------------|-------|-------------------|------------------|
| scene_01 | 1 | penetration_artifact | 1 | true |
| scene_02 | 0 | | 1 | true |
| scene_03 | 1 | stacking_instability | 1 | true |
| scene_04 | 0 | | 1 | true |
| scene_05 | 1 | impulse_chain_break | 2 | true |
| scene_06 | 0 | | 1 | true |
| scene_07 | 1 | friction_drift | 1 | true |
| scene_08 | 0 | | 1 | true |
| scene_09 | 1 | restitution_violation | 1 | true |
| scene_10 | 1 | stale_manifold | 1 | true |
| scene_11 | 2 | penetration_artifact, phase_mismatch | 1 | true |
| scene_12 | 0 | | 1 | true |
| scene_13 | 1 | layer_filter_miss | 1 | true |
| scene_14 | 1 | constraint_violation | 1 | false |
| scene_15 | 0 | | 1 | true |
| scene_16 | 1 | phase_mismatch | 1 | true |
| scene_17 | 0 | | 1 | true |
| scene_18 | 1 | tunneling | 1 | true |
| scene_19 | 1 | sleep_activation_error | 1 | true |
| scene_20 | 0 | | 1 | true |

`scene_11` must emit both `penetration_artifact` on the A-B contact and `phase_mismatch` on the A-C narrowphase pair in frame 0.
`scene_10` stale_manifold must appear on frame 3 with `bodies` `["m10"]`.
`scene_18` tunneling must appear on frame 1.

### Bundled violation records (normative)

The verifier compares full violation rows (kind, frame, bodies, detail) on bundled data:

| scene_id | kind | frame | bodies | detail |
|----------|------|-------|--------|--------|
| scene_01 | penetration_artifact | 0 | A, B | penetration 0.0025 m |
| scene_03 | stacking_instability | 2 | A, B | monotonic penetration growth |
| scene_05 | impulse_chain_break | 0 | A, C | impulse transfer below chain minimum |
| scene_07 | friction_drift | 0 | A, B | tangent impulse exceeds drift threshold |
| scene_09 | restitution_violation | 0 | A, B | restitution out of clamp |
| scene_10 | stale_manifold | 3 | m10 | manifold survived after contact removal |
| scene_11 | penetration_artifact | 0 | A, B | penetration 0.0020 m |
| scene_11 | phase_mismatch | 0 | A, C | narrowphase pair missing from broadphase |
| scene_13 | layer_filter_miss | 0 | A, B | layer masks do not intersect |
| scene_14 | constraint_violation | 0 | A, B | separation exceeds limit |
| scene_16 | phase_mismatch | 0 | A, B | narrowphase pair missing from broadphase |
| scene_18 | tunneling | 1 | A | displacement exceeds velocity threshold |
| scene_19 | sleep_activation_error | 0 | A | sleeping body moving too fast |

### Bundled `max_penetration_m` per scene

| scene_id | max_penetration_m |
|----------|-------------------|
| scene_01 | 0.0025 |
| scene_02 | 0.0005 |
| scene_03 | 0.0009 |
| scene_04 | 0.0004 |
| scene_05 | 0.0005 |
| scene_06 | 0.0005 |
| scene_07 | 0.0005 |
| scene_08 | 0.0005 |
| scene_09 | 0.0005 |
| scene_10 | 0.0005 |
| scene_11 | 0.002 |
| scene_12 | 0.0005 |
| scene_13 | 0.0005 |
| scene_14 | 0.0005 |
| scene_15 | 0.0005 |
| scene_16 | 0.0005 |
| scene_17 | 0.0005 |
| scene_18 | 0.0005 |
| scene_19 | 0.0005 |
| scene_20 | 0.0005 |

### Bundled stress replay tallies

| scene_id | replays_run | replays_passed | validated |
|----------|-------------|----------------|-----------|
| scene_10 | 1 | 1 | true |
| scene_13 | 1 | 1 | true |
| scene_14 | 1 | 1 | false |

All other bundled scenes: `replays_run` 0, `replays_passed` 0, `validated` true.

### Deterministic report bytes

The harness runs `/app/bin/contact-resolver` twice on `/app/scenarios/` and twice on
`PHYSICS_SCENE_DIR` swap fixtures. Each pair must write byte-identical reports.

### `PHYSICS_SCENE_DIR` fixtures

When `PHYSICS_SCENE_DIR` is set, still analyze only `scene_01` through `scene_20` and ignore
other `scene_*.json` files (for example `scene_99.json`). The directory may be an absolute path
or a symlink to the default scenarios tree; symlinked roots must produce the same bundled report
bytes as `/app/scenarios/`.

Fixture behaviors the harness exercises:

- **swap**: `scene_01.json` payload replaced with `scene_02.json` content while keeping `scene_id` `scene_01`.
- **probe**: `scene_07.json` replaced with `scene_04.json` events while keeping `scene_id` `scene_07`.
- **decoy**: extra `scene_99.json` present; summary `scenes_analyzed` remains 20 and no `scene_99` row appears.
- **symlink**: `PHYSICS_SCENE_DIR` is a symlink to `/app/scenarios`; report bytes match the default tree.
- **tolerance**: `scene_02.json` contact `penetration_m` set to `0.00105` (below `max_penetration_m` + `penetration_tolerance_m`); `scene_02` stays stable with zero violations.
- **broadphase_order**: `scene_16.json` `broadphase` uses `["B","A"]`; `scene_16` becomes stable (no `phase_mismatch`).
- **dedupe**: `scene_01.json` frame 0 lists the same contact twice; only one `penetration_artifact` row is emitted.
- **truncated_stress**: `scene_13.json` stress `frame_order` is `[0, 99]`; replay uses frame 0 only, but declared length 2 >= F=2 so `stress.validated` is false.
- **over_tolerance**: `scene_02.json` `penetration_m` is `0.00115`; emits one `penetration_artifact` with detail `penetration 0.0011 m`.
- **exact_boundary**: `scene_02.json` `penetration_m` is exactly `0.0011` (`max_penetration_m` + `penetration_tolerance_m`); stays stable.
- **restitution_separating**: `scene_02.json` positive restitution with separating normal velocity; detail `separating normal velocity with positive restitution`.
- **empty_contacts**: `scene_06.json` all frames have empty `contacts`; `impulse_chain_len` 0 and `max_penetration_m` 0.
- **contact_reorder**: `scene_05.json` lists `c2` before `c1`; after `contact_id` sort, `impulse_chain_len` remains 2 and `impulse_chain_break` bodies stay `["A","C"]`.
- **format_version**: `scene_02.json` includes `format_version` and non-zero `reserved`; bundled-stable behavior unchanged.
- **nested_decoy**: subdirectories and extra top-level `scene_88.json` present; summary counts unchanged from bundled defaults.
- **full_stress_scene_10**: `scene_10.json` stress `frame_order` is `[0,1,2,3,4]`; `stress.validated` false while `stale_manifold` still reported.
- **frames_reordered**: `scene_03.json` `frames[]` reversed (2,1,0); `stacking_instability` absent and `scene_03` stable.
- **semicolon_body_id**: `scene_02.json` body id `A;cmd` with semicolon; remains stable; violation `bodies` arrays preserve the literal id.
- **duplicate_contact_id**: `scene_01.json` frame 0 lists two contacts sharing `contact_id` `c1` on different body pairs (`A-B` and `X-Y` where `X`/`Y` are absent from `bodies`); emit separate `penetration_artifact` rows (no dedupe across different body pairs; missing body ids skip layer check).
- **capture_metadata**: `scene_02.json` includes `capture_checksum` and `payload_len`; replay unchanged, stays stable.
- **empty_stress_order**: `scene_13.json` stress `frame_order` is `[]`; schedule passes with zero replay violations, `validated` true.
- **mixed_stress_schedules**: `scene_13.json` adds schedule `[0,1]` alongside prefix `[0]`; not all schedules span all frames, `validated` true.
- **tunneling_sub_limit**: `scene_18.json` frame-1 `A` x-position `0.5`; displacement below policy limit, `scene_18` stable.
- **backtick_body_id**: `scene_02.json` body id ``A`x` ``; remains stable with literal id preserved in JSON keys.
- **duplicate_frame_index**: `scene_03.json` inserts a second `frame` 0 entry before the bundled frames; stacking evaluated along `frames[]` order — `stacking_instability` at frames 1 and 2 (shifted window).
- **horizontal_normal**: `scene_02.json` separating velocities with `normal_y` 0.3 and positive restitution; no `restitution_violation` (`normal_y` must exceed 0.5).
- **restitution_once_per_pair**: `scene_02.json` two contacts on the same A-B pair with separating velocities; one `restitution_violation` row only.
- **sleep_diagonal_over**: `scene_19.json` sleeping `A` velocity `[0.008, 0.008]`; `hypot` exceeds threshold, `sleep_activation_error` on frame 0.
- **sleep_diagonal_under**: `scene_19.json` sleeping `A` velocity `[0.005, 0.005]` with `B` at `[0.0, 0.005]`; `hypot` below threshold and no separating restitution, `scene_19` stable.
- **absolute_path**: `PHYSICS_SCENE_DIR` set to the resolved absolute path of `/app/scenarios`; report bytes match the default tree.
- **approaching_restitution**: `scene_02.json` positive restitution with approaching normal velocity (`A` `[0,-0.2]`, `B` `[0,0.1]`); stays stable (relative normal velocity not positive).
- **restitution_swapped_bodies**: `scene_02.json` contact `body_a`=`B`, `body_b`=`A` with velocities `B` `[0,0.2]`, `A` `[0,-0.1]`; one separating `restitution_violation` with bodies `["B","A"]`.
- **missing_only_stress**: `scene_13.json` stress `frame_order` `[99,100]`; replay finds no frames (passes vs baseline) but declared length 2 >= F so `validated` false.
- **metadata_plus_restitution**: `scene_02.json` has `format_version`, non-zero `reserved`, `capture_checksum`, `payload_len`, plus separating velocities; still emits separating `restitution_violation`.
- **permission_denied_decoy**: unreadable `scene_99.json` in `PHYSICS_SCENE_DIR`; report bytes match bundled default.

### Build and stub checks

From `/app`, `make build` must succeed and `/app/bin/contact-resolver` must exceed 2048 bytes.
Do not modify `/app/replay/main.go`. Source must not retain `solver.AnalyzeScene not implemented`.
