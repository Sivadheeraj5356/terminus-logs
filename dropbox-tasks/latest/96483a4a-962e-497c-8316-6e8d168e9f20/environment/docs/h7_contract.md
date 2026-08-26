# h7 ladder replay contract

## Tools

Rebuild: `bash /app/environment/scripts/build_all.sh`  
Ladder: `bash /app/environment/scripts/run_ladder.sh`  
Probe: `bash /app/environment/scripts/probe_play.sh <map.json> <step,step,...>`

Literals: `ROOT=/app/environment`, `BIN=/app/environment/bin`, `SIM=${BIN}/h7_sim`, `H7D=${BIN}/h7d`.

## Graded suite

`fixtures/maps/ladder_suite.json` lists graded `seed_id` values. Each graded map JSON beside it already includes `steps`. Training/puzzle trees are probe-only.

## Report shape

Top-level `{ "rows": [ ... ] }` sorted by `seed_id`. Each row:

| field | type | meaning |
|-------|------|---------|
| seed_id | string | map id |
| path_stamp | string | first 8 hex of sha256 over `q,r;q,r;...` including start |
| tick_total | uint | movement steps executed |
| cost_total | uint | replay cost binding below |
| wrap_events | uint | steps whose raw neighbor left the board and remapped |
| portal_hops | uint | teleports that actually fired |
| replay_digest | string | 64 hex sha256 of compact JSON `ticks` array from the sim |

## Board orientation

Maps set `orient` to `pointy` or `flat`. Neighbor deltas for step indices 0..5 depend on orientation:

- pointy: (1,0), (1,-1), (0,-1), (-1,0), (-1,1), (0,1)
- flat: (1,0), (0,-1), (-1,-1), (-1,0), (0,1), (1,1)

## In-board remapping

After applying a neighbor delta, both coordinates must land inside `[0, width)` and `[0, height)`. Negative raw coordinates land on the far edge (same rule as Euclidean remainder on each axis).

## Portals

Each portal has `from`, `to`, and `arms` (list of legal entry step indices). A teleport fires only when the post-remap cell equals `from` **and** the step index used this tick is listed in `arms`. Walking onto `to` never reverse-fires.

At most one teleport resolves per movement tick. Landing on another portal's `from` does not chain inside the same tick.

## Wet rim

Maps set `wet_window` (uint). When a tick remaps across the board edge, the next `wet_window` **non-portal** landings pay double the terrain table value (integer). The remapping tick itself counts toward that window. Portal ticks do not pay movement cost and do not consume wet charges.

Default terrain is 1 when a cell is absent from the table. Keys use `q,r`.

## Cost binding

Report `cost_total` sums each tick's `step_cost` except ticks with `via_portal=true` (those contribute 0). The Go replay session must honor the sim's `via_portal` flag polarity as emitted.

## Tick records

`tick`, `q`, `r`, `step_cost` (post-wet terrain at the landing cell), `via_portal`.
