# Field rules

The g2 suite is a scientific simulation ledger over dual-plane visibility replay on a rectangular grid, cadence-gated fade of stale coverage, ally observer pooling, and resident-memory accounting.

## Grid geometry

Every scenario declares `slots`, `grid_width`, and `grid_height` with `slots == grid_width * grid_height`. Slot index `i` maps to column `i % grid_width` and row `i / grid_width`. Observer coordinates must satisfy `cx < grid_width` and `cy < grid_height`. Visibility reach uses Manhattan distance on that coordinate system.

## Dual-plane replay

The ledger stores two independent bitplanes under `bitplane_digests`:

- `plane_a` — persistent **explored** coverage for the whole run
- `plane_b` — **sensor** visibility for the final tick only

Required behavior each tick:
1. Build the current-tick sensor/lit mask from active observers (Manhattan reach on the declared grid).
2. OR-merge lit cells into explored: explored bits only turn on, never off. Previously explored cells remain explored after sensors leave.
3. Keep sensor/lit tick-local: do **not** copy explored into sensor, and do **not** replace explored with the current lit mask.
4. After sensors leave a cell, fade may still present stale lit residue for that tick, but the explored plane itself must retain the bit.

Observable consequences for multiphase scenarios (for example shrinking reach after a phase boundary):
- `bitplane_digests.plane_a != bitplane_digests.plane_b`
- final `explored_count` is typically greater than `sensor_count`
- `stale_count = explored_count - sensor_count` is positive when coverage was lost
- `plane_delta_digest` hashes every slot where explored and sensor differ as `idx:<i>:a:<explored_bit>:b:<sensor_bit>`, or `delta:none` when none differ

Aliasing the planes (setting explored equal to lit/sensor each tick) violates this contract even if the binary still builds and emits a ledger.

## Observer phase windows

When `observer_phases` is present, phases are ordered by ascending `until_tick`. Phase intervals are half-open on the right: a phase covering ticks in `[prev, until_tick)` is active while `tick < until_tick`. The tick equal to `until_tick` belongs to the next phase, not the current one. The first phase starts at tick 0. After the last boundary, the last phase remains active for all later ticks. If `until_tick` values are not strictly increasing, treat the scenario as having no active observers (empty set) for the run.

Examples for a phase with `until_tick = 80` followed by another phase:
- tick `79` → still the first phase (`79 < 80`)
- tick `80` → second phase (`80 < 80` is false)
- tick `81` → second phase

Using inclusive checks such as `tick <= until_tick` is incorrect and shifts every boundary by one tick, which changes explored/sensor/stale counts and cadence traces for multiphase fixtures.

## Mode-aware cadence

Each mode provides `decay_modulus` and `decay_phase`. When `decay_modulus == 0`, fade counters never decay. Otherwise counters saturating-decrement by 1 only when `tick_ix % decay_modulus == decay_phase % decay_modulus`. Sensor-active cells refresh to `fade_start` after the cadence step for that tick. Fade counters for each scenario start at that mode's `fade_start` on every slot before tick 0.

Two related but distinct string formats are required:

1. Cadence entry (stored in `cadence_trace`, and used as the checksum input):

`tick:<tick_ix>:step:<0|1>:sum:<counter_sum>`

Example: `tick:2:step:1:sum:48`

2. Provenance row (stored in `cadence_trace_v3`):

`tick:<tick_ix>:decay:<0|1>:fade_checksum:<hex16>`

Example: `tick:2:decay:1:fade_checksum:<sha16("tick:2:step:1:sum:48")>`

Notes:
- The boolean flag uses the token `step` inside `cadence_trace` and the token `decay` inside `cadence_trace_v3`; both carry the same 0/1 value for that tick.
- `cadence_trace_v3` is a **full-run** array: length equals the simulation tick count (120 for the certifying emit). It is **not** truncated to the last 12 entries.
- For each `cadence_trace_v3[i]` row, `fade_checksum` is the first 16 hex chars of SHA256 over **only that tick's cadence entry** (the `tick:…:step:…:sum:…` string for tick `i`). It is never:
  - a hash of the `cadence_trace_v3` row itself,
  - a join of all 120 cadence entries,
  - or a join of the retained last-12 `cadence_trace` tail.
- The separate run-level field `fade_checksum` (sibling of `cadence_trace`, not inside v3 rows) is the first 16 hex chars of SHA256 over the **retained last-12** `cadence_trace` entries joined by `|`.
- Top-level `cadence_digest` aggregates the **full** `cadence_trace_v3` arrays across runs. Rebuilding v3 checksums from the truncated `cadence_trace` tail will fail verification.

## Ally observer pooling

Ally groups are canonicalized by sorting unique observer ids. The shared pool handle is the lowest oid in that canonical set. Identical groups (including reordered ids) reuse one allocation; `copies` is always `1`. Resident footprint is cumulative across distinct allocated groups:

`bytes_used = slots * cell_bytes + distinct_groups * group_header_bytes + total_memberships * observer_metadata_bytes`

where `total_memberships` is the sum of canonical group lengths over distinct allocated groups (an oid in two groups contributes once per group membership). `merge_lineage` records one row per distinct group on first allocation.

`pool_trace` is a per-tick provenance stream: for every simulation tick, emit one row for every declared ally group (in declaration order), even when the group was already allocated earlier. Each row uses the sorted observer list and the cumulative `bytes_used` after that tick's pool step:

`group:<gid>:observers:<comma_ids>:handle:<handle_id>:copies:<copies>:bytes:<bytes_used>`

Field meanings:
- `gid` is the **0-based declaration index** into `ally_groups` (first group is `0`, second is `1`, …). It is **not** the pool handle and **not** an observer oid.
- `handle` is the shared pool handle (lowest oid in the canonical group).
- `observers` is the canonical sorted unique oid list for that group.

## Trace retention

Full-length traces (one entry per tick for the whole run):
- `plane_trace`
- `cadence_trace_v3`
- `pool_trace`

Trailing windows retained in the ledger (older ticks dropped):
- `decay_trace`: last **8** fade-sum values
- `cadence_trace`: last **12** cadence entries
- `resident_trace`: last **12** `tick:<tick_ix>:bytes:<bytes_used>` entries

## Resident memory band

`peak_resident_bytes` is the high-water resident footprint across all g2 runs. `footprint_band` is `WITHIN` when peak is at or below the active mode `resident_cap`, otherwise `OVER`.

## Tick batch parsing

`--ticks HIGH:LOW` expands with multiplication against the `r0` mode `tick_scale`:

`ticks = HIGH * r0.tick_scale + LOW`

With the shipped `r0` (`tick_scale = 10`), the certifying argument `12:0` therefore means **120** simulation ticks, not 12. Storing the literal `12` from the string is incorrect.

Exactly zero or one colon separators are allowed. Both components must be non-negative integers when a colon is present; a plain non-negative integer is also accepted.

Malformed arguments must exit **non-zero** and print a non-empty message on **stderr**. Rejected examples include:
- `:1` or `1:` (empty HIGH or LOW)
- `a:b` (non-integers)
- `1:2:3` (more than one colon)
- empty string
- values that overflow `u64` arithmetic when scaled

Soft defaults (treating parse failure as `0` or `12`) are not allowed.

## schema_version 3 provenance

Top-level fields include `plane_trace_digest`, `cadence_digest`, `pool_trace_digest`, and `scenario_digest`.

Per-run fields:
- `plane_trace`: `tick:<tick_ix>:sensor:<sensor_count>:explored:<explored_count>:stale:<stale_count>` (full run)
- `cadence_trace_v3`: `tick:<tick_ix>:decay:<0|1>:fade_checksum:<hex16>` (full run; per-row checksum is over that tick's cadence entry alone)
- `pool_trace`: per-tick per-group rows as above (full run)
- `source_refs`: sorted + deduped source paths for the run. Required set for every run:
  - `cases/g2/<scenario_id>.json`
  - `specs_r/<mode>.toml`
  - `docs/field_rules.md`
  - `docs/api.md`
  - `docs/lex_k.tsv`
- `run_v3_digest`: sha16 of `scenario_id|run_digest|plane_trace_joined_by_;|cadence_trace_v3_joined_by_;|pool_trace_joined_by_;|source_refs_joined_by_;`

Aggregate digests (all row lists sorted before hashing):
- `plane_trace_digest` / `cadence_digest` / `pool_trace_digest`: sha16 over sorted `scenario_id|sha16(joined_trace)` rows, where `joined_trace` is the full `plane_trace` / full `cadence_trace_v3` / full `pool_trace` joined by `;`
- `scenario_digest`: sha16 over sorted `relative_path|sha256(file_bytes)` rows for `cases/g2/*.json` and `specs_r/*.toml`
- `ledger_digest`: full sha256 of exactly this payload (legacy run-pair-only folds are wrong):

```text
{sorted scenario_id:run_digest joined by ;}|orchestrator:{orch csv}|worker:{worker csv}|plane:{plane_trace_digest}|cadence:{cadence_digest}|pool:{pool_trace_digest}|scenario:{scenario_digest}
```

Omitting the four `|plane:…|cadence:…|pool:…|scenario:…` segments, or hashing only sorted `scenario_id:run_digest` pairs, does not satisfy schema_version 3.

## Recovery epoch

Recovery state lives at `/app/environment/state/recovery_epoch` as a decimal integer file. Correctness has two workspace pieces:

1. Emitter reader: when building the ledger, stamp every run with the current epoch value.
2. Grader recovery hook: `/app/environment/docs/recover_k.txt` must implement the increment protocol below. The hook is part of the shipping contract and must match this semantics even though you must not invoke it during normal certification.

### How the grader runs `recover_k.txt`

The grader does **not** source or execute the file as one multi-line shell script. Instead it:

1. Reads the file line by line
2. Skips blank lines and lines whose first non-space character is `#`
3. Runs **each remaining line as its own** `bash -lc '<that single line>'` subprocess

Therefore every executable line must be fully self-contained. Shell variables, `cd`, or `export` from one line do **not** survive into the next line. A multi-line script that sets `cur=...` on one line and uses `$cur` on the next will fail. Prefer a single executable line (or independently complete one-liners) that performs mkdir, read, validate, increment, and write without relying on prior-line state.

### Protocol

- Missing file → emit stamps every run with `recovery_epoch = 0`
- Non-decimal or empty file → emit still stamps `0` and does not rewrite the file
- Ordinary certification emits never create or increment the file
- The recovery hook must: ensure `state/` exists; read the current counter (treat missing as `0`); reject non-decimal content with a non-zero exit; write `current + 1` back to `/app/environment/state/recovery_epoch`
- Successive recoveries yield epochs `1`, `2`, …
- Touching a boolean flag file (for example `recovered.flag`) is not a valid implementation of this contract
- `purge_k.sh` clears `/app/environment/state/` (including the epoch file)

Do not run purge or recovery during normal certification; still ensure the hook and reader both implement the protocol.
