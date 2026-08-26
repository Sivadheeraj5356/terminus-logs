The hex skirmish adjudicator under `/app/environment/skirmish` resolves battle scenarios into a deterministic transcript. Current rebuilds disagree with the rulebook on interrupt chains, vision, and armor interactions. Repair the Rust sources under `/app/environment` so `/app/bin/skirmish` regenerates reports that match the contract below. Static report writes are not enough; the verifier rebuilds from source and re-runs adjudication.

Work from `/app`. Build and run only through `/app/bin/skirmish` (it rebuilds with `cargo build --release --locked` from `/app/environment/skirmish` before executing). Offline only.

```
/app/bin/skirmish adjudicate --scenario <scenario.json> --out <report.json>
```

Exit `0` for a resolved fight, `2` when the scenario itself is invalid. On success or invalid, always write `/`-absolute `--out` JSON.

Scenario JSON object fields:
- `map`: `{ "width": int, "height": int, "elevation": int[height][width], "blocked": bool[height][width] }`
- `units`: array of `{ "id": string, "team": string, "hex": [x,y], "hp": int, "armor": int, "speed": int, "vision": int, "range": int, "traits": string[], "actions": string[] }`
- `beacons`: array of `{ "hex": [x,y], "radius": int, "team": string }` (may be empty)

Coordinates are axial-ish grid cells with `0 <= x < width` and `0 <= y < height`. Hex distance is `max(dx, dy, dx+dy)` after converting cube coords `(x, y, -x-y)` — use `dx=|x1-x2|`, `dy=|y1-y2|`, `dz=|(x1+y1)-(x2+y2)|`, then `max(dx,dy,dz)`.

Adjudication rules:
1. Reject as invalid (status `INVALID`) when any unit hex is out of bounds, on a blocked cell, or two units share a hex. Prefer reason `OOB`, then `BLOCKED`, then `OVERLAP` when more than one applies (check units in ascending `id`).
2. Initiative order: descending `speed`, ties broken by ascending `id`.
3. Process units in initiative order. For each living unit, emit `TURN_START`, then attempt each listed action in order. If the unit dies or morale-breaks mid-turn, drop remaining actions.
4. `MOVE` actions are spelled `MOVE:x,y` (example `MOVE:2,1`). The destination must be one of the six neighbors `[x+1,y], [x-1,y], [x,y+1], [x,y-1], [x+1,y-1], [x-1,y+1]` of the unit's current hex, in bounds, not blocked, and unoccupied. Emit `MOVE` with `from`/`to`. Illegal move emits `ACTION_FAIL` with `detail`=`ILLEGAL_MOVE` and skips that action only.
5. Immediately after a successful `MOVE`, resolve overwatch: every living enemy that has trait `OVERWATCH`, has line-of-sight to the mover's new hex, is within `range`, and can see the mover under vision rules fires one free strike before the mover continues. Overwatch actors fire in ascending `id`. Each overwatch strike uses the strike damage rules and emits `OVERWATCH` (not `STRIKE`).
6. `STRIKE` needs a chosen target: the nearest visible living enemy by hex distance, ties broken by ascending enemy `id`. Must have LOS and distance `<= range`. Emit `STRIKE` with `target` and `damage`. If none qualify, `ACTION_FAIL`/`NO_TARGET`.
7. Damage is `max(1, 4 - target.armor)` unless attacker has `PIERCE`, in which case damage is exactly `4`. Apply to `hp`. If `hp <= 0`, emit `DOWNED` and remove the unit from the board. If after damage `0 < hp < 3`, the target morale-breaks: emit `MORALE_BREAK` and cancel that target's remaining actions if its turn is later or still in progress.
8. `GUARD` emits `GUARD` and adds `+1` armor until that unit's next `TURN_START` (then armor returns to its scenario base before other logic).
9. Vision: allies are always visible. An enemy is visible if hex distance `<=` observer `vision`, or the enemy hex lies within any beacon of the observer's team (`distance <= radius`). Strikes and overwatch require visibility.
10. LOS: cells on the inclusive hex line from attacker to target (see `hex_line` in the codebase docs) must not be blocked. A cell with elevation `>= max(start_elev, end_elev) + 1` also blocks, except the start and end cells themselves.
11. Unknown action strings emit `ACTION_FAIL`/`UNKNOWN_ACTION`.

Report JSON (all fields required):
- `schema_version`: number `1`
- `status`: string `RESOLVED` or `INVALID`
- `invalid_reason`: `null` on resolve, else one of `OOB`|`BLOCKED`|`OVERLAP`
- `initiative`: string array of unit ids in order (empty when `INVALID`)
- `events`: array of event objects in resolution order; each has number `seq` starting at `0`, string `kind`, and kind-specific fields as emitted above (`actor`, `from`, `to`, `target`, `damage`, `detail` only when relevant)
- `survivors`: array of `{ "id", "hp", "hex", "armor" }` for living units, sorted by ascending `id`; `armor` is the effective armor at end of fight
- `transcript_digest`: string `sha256:` plus lowercase hex digest of the UTF-8 bytes of `events` serialized as compact JSON with object keys sorted lexicographically at every object (no spaces)

Event `kind` values used: `TURN_START`, `MOVE`, `STRIKE`, `OVERWATCH`, `GUARD`, `DOWNED`, `MORALE_BREAK`, `ACTION_FAIL`.
