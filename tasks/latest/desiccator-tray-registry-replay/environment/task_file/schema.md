# Desiccator tray registry specification

## Output JSON shape

Write UTF-8 JSON with two-space indent, sorted keys at every object level, and a trailing newline.

Top-level keys in sort order: `duplicate_events`, `invalid_lines`, `rejected_events`, `summary`, `trays`.

`duplicate_events[]` — each object includes `event_id` (string), `ordinal` (discovery integer), `reason` (always `DUPLICATE_EVENT`).

`invalid_lines[]` — JSON array of discovery ordinals (integers) for lines that fail the five-field layout.

`rejected_events[]` — each object includes sorted keys `event_id`, `line` (1-based line number in `source`), `ordinal` (discovery), `reason`, and `source` (absolute path to the `.tray` shard).

`trays[]` — sorted by `tray_id`; each object includes `capacity_units`, `cycles_since_regen`, `held`, `locked`, `regen_every`, `sealed`, `tier`, `tray_id`, `units`.

`summary` — object with sorted integer keys: `applied_events`, `duplicate_events`, `invalid_lines`, `loads_applied`, `rejected_events`, `total_lines`, `unloads_applied`. `loads_applied` equals accepted `LOAD` count; `unloads_applied` equals accepted `UNLOAD` count.

## Duplicate event handling

Trim `event_id`; if non-empty and already in the accepted set, emit `DUPLICATE_EVENT`. Rejected lines do not consume ids.

## Tray held scope

`TRAY_HELD` blocks `LOAD`, `UNLOAD`, `REGEN`, `SEAL`, and `OPEN` while `held` is true; it does not block `LOCK`, `UNLOCK`, `HOLD`, or `RELEASE`.

## Tray locked scope

`TRAY_LOCKED` blocks every operation except `LOCK` and `UNLOCK` while `locked` is true.

## Regeneration gating

`REGEN` clears `units` to zero, clears `sealed`, and resets `cycles_since_regen` to zero. Reject `REGEN_BLOCKED` when **any** tray with a lower `tier` has `units > 0` (not merely the adjacent tier).

## Load and unload

`LOAD` adds positive integer `units`, rejects `OVER_CAPACITY` when the sum would exceed `capacity_units`, and increments `cycles_since_regen` on success. `UNLOAD` subtracts positive integer `units`; reject `EMPTY_TRAY` when `units` is zero, `UNDERFLOW` when the request exceeds current `units`.

## Seal and open

`SEAL` requires `units > 0` and rejects `BAD_STATE` when already sealed. `OPEN` requires `sealed` and rejects `BAD_STATE` when not sealed.

## CLI

Zero arguments → `/app/task_file`. One argument → that task root. Two or more → fatal exit 1 preserving `/app/output/registry.json`.

## Fatal conditions

Missing `trays.json` or `events/`; no `.tray` files; invalid UTF-8; malformed `trays.json`.

## Event lines

Five tab fields: `event_id`, `op`, `tray_id`, `units`, `lot_tag` (trim fields). Trailing empty tab → `invalid_lines`.

Ops: `LOAD`, `UNLOAD`, `REGEN`, `SEAL`, `OPEN`, `LOCK`, `UNLOCK`, `HOLD`, `RELEASE`.

| op | `units` | `lot_tag` |
|----|---------|-----------|
| `LOAD`, `UNLOAD` | required positive int | empty |
| `REGEN`, `SEAL`, `OPEN`, `LOCK`, `UNLOCK`, `HOLD`, `RELEASE` | empty | empty |

## Discovery and replay order

Recursively discover lowercase `.tray` files under `events/`. Normalize physical line endings: treat `\r\n`, bare `\r`, and `\n` each as ending one logical line. Sort shard paths lexicographically; within each shard replay lines in file order (1-based physical line numbers after normalization).

## Reject precedence

Evaluate in order; first match wins:

`BAD_EVENT` → `DUPLICATE_EVENT` → `UNKNOWN_OP` → `UNKNOWN_TRAY` → `BAD_LINE` → `TRAY_LOCKED` → `TRAY_HELD` → `BAD_UNITS` → op-specific (`OVER_CAPACITY`, `UNDERFLOW`, `EMPTY_TRAY`, `REGEN_BLOCKED`, `BAD_STATE`).

## Seed snapshot

`summary.total_lines` **14**, `applied_events` **12**, `rejected_events` **2**, `duplicate_events` **0**, `invalid_lines` **0**, `loads_applied` **4**, `unloads_applied` **2**.

`d009` → `TRAY_LOCKED` ordinal **8** in `/app/task_file/events/beta/02_more.tray` line **4**.

`d011` → `UNKNOWN_OP` ordinal **10** in `/app/task_file/events/runtime/zz_live.tray` line **1**.

Final trays: `alpha` **4** units, not sealed, `cycles_since_regen` **2**; `beta` **4** units; `gamma` **1** unit.
