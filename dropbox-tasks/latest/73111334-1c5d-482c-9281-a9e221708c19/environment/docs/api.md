# Public API

- `forge_all.sh` builds the workspace and installs `k7` to `/app/bin/k7`.
- `run_k7.sh --suite g2 --ticks HIGH:LOW --emit PATH` drives the g2 suite.
- `/app/bin/k7 --suite g2 --ticks 12:0 --emit /app/output/session_ledger.json` is the certifying invocation (120 ticks with `r0` `tick_scale = 10`).
- `run_k7.sh probe --suite g2` runs the quick preview path.
- Scenario fixtures are discovered from `cases/g2/*.json` at runtime.
- Mode specs are loaded from `specs_r/<mode>.toml`.

## Mode TOML fields

Required keys:
- `mode`, `resident_cap`, `decay_modulus`, `decay_phase`
- `tick_scale`, `cell_bytes`, `fade_start`
- `group_header_bytes`, `observer_metadata_bytes`

## Scenario JSON fields

Required keys:
- `id`, `mode`, `observers`, `ally_groups`, `slots`, `grid_width`, `grid_height`
- optional `observer_phases` with `{ until_tick, observers }`

`slots` must equal `grid_width * grid_height`. Observer `cx` / `cy` must lie inside the grid.

## Tick argument

Accepted forms:
- `N` — plain non-negative integer tick count
- `HIGH:LOW` — exactly one colon; both sides non-negative integers; value is `HIGH * r0.tick_scale + LOW` (multiplication, not addition or concatenation)

Example with shipped `r0` (`tick_scale = 10`): `--ticks 12:0` → `12 * 10 + 0 = 120`. The ledger top-level `ticks` field must be `120`, not `12`.

Rejected forms must exit non-zero with a non-empty stderr message. Concrete rejects include `:1`, `1:`, `a:b`, `1:2:3`, and `""`. Soft-defaulting malformed input is not allowed.

## Dual-plane digests

`bitplane_digests.plane_a` digests the persistent explored plane; `bitplane_digests.plane_b` digests the final-tick sensor plane. After runs where sensors shrink (phase changes), these digests must differ and `explored_count` is typically greater than `sensor_count`. Replacing explored with the current lit/sensor mask each tick is invalid.

## Recovery state

- Path: `/app/environment/state/recovery_epoch`
- Contents: decimal integer epoch counter
- Missing → emit uses `0` on every run row
- Ordinary emits do not increment the counter
- Grader recovery increments by one and rewrites the file (`0 → 1 → 2 → …`)
- `purge_k.sh` clears `/app/environment/state/` (including the epoch file) and `/app/output/`
- Hook file: `/app/environment/docs/recover_k.txt` must implement the epoch-increment protocol from `field_rules.md` (write `recovery_epoch`, not a boolean flag).
- Invocation model: the grader runs each non-comment line as a separate `bash -lc` command. Lines cannot share shell variables. Prefer one self-contained executable line.
- Do not invoke the hook during normal certification, but the shipped hook must be correct.

## Cadence string formats

- `cadence_trace` entry: `tick:<tick_ix>:step:<0|1>:sum:<counter_sum>` (retained last 12 in the ledger)
- `cadence_trace_v3` row: `tick:<tick_ix>:decay:<0|1>:fade_checksum:<sha16(that tick's cadence_trace entry)>`
- `cadence_trace_v3` length equals the full tick count (120 for certifying emit); do not truncate it to 12
- Per-row `fade_checksum` hashes only that tick's `step`/`sum` entry — never the retained tail join and never the v3 row text
- Run-level `fade_checksum` hashes the retained last-12 `cadence_trace` joined by `|`
- Do not put `decay` inside `cadence_trace`

## Trace retention (ledger fields)

| Field | Retention |
|---|---|
| `plane_trace` | full run (one row per tick) |
| `cadence_trace_v3` | full run (one row per tick) |
| `pool_trace` | full run (one row per ally group per tick) |
| `decay_trace` | last 8 fade-sum values |
| `cadence_trace` | last 12 cadence entries |
| `resident_trace` | last 12 resident entries |

## Checksums and ledger_digest

- Per-tick `cadence_trace_v3.fade_checksum`: sha16 of that tick's `cadence_trace` entry (`tick:…:step:…:sum:…`) alone
- Run-level `fade_checksum`: sha16 of the retained `cadence_trace` entries joined by `|`
- Tick argument reminder: `HIGH:LOW` means `HIGH * r0.tick_scale + LOW` (multiplication, not addition); certifying `12:0` → `120`
- `ledger_digest` must include the four v3 aggregate digests:

```text
{sorted scenario_id:run_digest joined by ;}|orchestrator:{…}|worker:{…}|plane:{plane_trace_digest}|cadence:{cadence_digest}|pool:{pool_trace_digest}|scenario:{scenario_digest}
```

A digest over only sorted `scenario_id:run_digest` pairs is a legacy fold and must not match.

## pool_trace group field

In `group:<gid>:observers:…:handle:…`, `gid` is the 0-based index of the group inside `ally_groups`. Do not put the handle oid in the `group:` slot.

## source_refs

Every run must list these paths, sorted and deduplicated:

- `cases/g2/<scenario_id>.json`
- `specs_r/<mode>.toml`
- `docs/field_rules.md`
- `docs/api.md`
- `docs/lex_k.tsv`

## session_ledger.json schema_version 3

Top-level fields:
- `schema_version`, `suite`, `ticks`, `peak_resident_bytes`, `resident_cap_bytes`, `footprint_band`
- `runs`, `orchestrator_phases`, `worker_phases`, `source_digest`, `phase_digest`, `ledger_digest`
- `plane_trace_digest`, `cadence_digest`, `pool_trace_digest`, `scenario_digest`

### merge_lineage rows

```json
{"group": [10, 11], "handle": 10, "copies": 1}
```

- `group`: canonical sorted unique observer ids
- `handle`: lowest oid in the canonical group
- `copies`: always `1`

Per-run fields:
- v2: `scenario_id`, `footprint_band`, `peak_bytes`, `bitplane_digests`, `merge_lineage`, `decay_trace`,
  `explored_count`, `sensor_count`, `stale_count`, `fade_checksum`, `observer_pool_digest`,
  `plane_delta_digest`, `cadence_trace`, `resident_trace`, `recovery_epoch`, `run_digest`
- v3: `plane_trace`, `cadence_trace_v3`, `pool_trace`, `source_refs`, `run_v3_digest`

JSON skeleton:
```json
{
  "schema_version": 3,
  "suite": "g2",
  "ticks": 120,
  "runs": [
    {
      "scenario_id": "c1",
      "decay_trace": [/* last 8 */],
      "cadence_trace": [/* last 12 */],
      "resident_trace": [/* last 12 */],
      "plane_trace": ["tick:0:sensor:..."],
      "cadence_trace_v3": ["tick:0:decay:1:fade_checksum:..."],
      "pool_trace": ["group:0:..."],
      "source_refs": [
        "cases/g2/c1.json",
        "docs/api.md",
        "docs/field_rules.md",
        "docs/lex_k.tsv",
        "specs_r/r0.toml"
      ],
      "run_v3_digest": "..."
    }
  ],
  "plane_trace_digest": "...",
  "cadence_digest": "...",
  "pool_trace_digest": "...",
  "scenario_digest": "..."
}
```
