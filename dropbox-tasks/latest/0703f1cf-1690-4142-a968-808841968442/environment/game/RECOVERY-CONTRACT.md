# glyph-mill recovery pipeline — output contract

Notes for whoever ends up rebuilding the recovery tooling against this
install. Field names below are fixed since other scripts key off them
downstream — don't rename anything, and don't drop a field just because it
looks redundant with something else.

## `discover`

Writes one JSON object to `--out`:

```
{
  "schema_version": 1,
  "rooms": [ { ... }, ... ]
}
```

`rooms` is sorted by room id. Each entry:

- `room`, `title`, `glyphs`, `max_moves` — copied straight from that room's
  LMDB hint record (`glyphs` is the list of strings, `max_moves` an int).
- `lmdb_key` — the key the hint record is stored under, `room:<id>`.
- `loaded_files` — absolute paths under the given root, sorted, of every
  rule file the runtime actually loads for that room, and nothing loaded
  for any other room.
- `trace_excerpt` — a non-empty list of raw lines showing genuine runtime
  observation of the resolution for that room (e.g. an `openat()`-style
  syscall line, an `lsof`-style row, or equivalent). Each line has to
  reference at least one of `loaded_files` and look like real tracer
  output — a summary doesn't count, and neither does a line assembled from
  a static path computation that never actually observed the process.

## `normalize`

Writes one JSON object to `--out`:

```
{
  "schema_version": 1,
  "grid": {
    "width": 8,
    "height": 7,
    "directions": {"north": [0, -1], "east": [1, 0], "south": [0, 1], "west": [-1, 0]}
  },
  "rooms": [ { ... }, ... ]
}
```

`width`/`height` come from the core rules YAML's `grid` table. `directions`
is a **separate, top-level key in that same YAML file** (a sibling of
`grid`, not nested inside it) — it's a dict from direction name to its
`[dx, dy]` vector, copied over as that same dict, not flattened to a list
of names. `rooms` is sorted by room id. Each room object, sourced from
whatever `discover` already resolved for
that room plus the rule files it points at:

- `room`, `title`, `start`, `target`, `salt`, `palette`, `pack`, `glyphs`,
  `max_moves` — straight off the room's LMDB hint record.
- `beacons` — the hint record's `beacons` object (path-index string keys,
  integer cell values), or `{}` if the record has none.
- `glyph_values` — every symbol in the room's palette YAML `symbols`
  table, not only the room's own glyphs, sorted by key, values cast to
  int.
- `mask` — the palette YAML's `mask` value, as an int.
- `cycle`, `pivot` — the room's pack TOML `[walk]` table's `cycle` (list of
  direction strings) and `pivot`.
- `stride` — the pack TOML `[walk]` table's `stride`, unless the room's own
  LMDB hint record carries a `stride_override` field, in which case that
  value takes precedence for that room.
- `turn_bias` — the core rules YAML `turns` table entry keyed by `pivot`.
- `overlay` — the stem (no directory, no `.yaml`) of whichever overlay
  file `discover` resolved for this room.
- `mask_shift`, `rotation` — from that same overlay file.
- `loaded_files` — the same list `discover` already reports for the room.

This has to reflect whatever's live on disk for the given root, not a
cached answer — if hints or rule files get edited afterward (including an
edit that flips which overlay the runtime picks), re-running `normalize`
needs to show the new values.

## `solve`

Writes one JSON object to `--out`:

```
{
  "schema_version": 1,
  "rooms": [ { "room": ..., "glyphs": [...] }, ... ]
}
```

Sorted by room id. `glyphs` here is the move sequence for that room (not
the room's available glyph set).

### Walk transition

`replay` (and the runtime behind it) advances a room's walker one cell per
glyph in the sequence. For move `index` (0-based) with glyph `g`, starting
from cell `state` (row-major: `state = y * width + x`) and the previous
move's direction index `prev` (`null` for the first move in a room), the
runtime picks one entry out of `cycle` — call its position `dindex` — and
applies that direction's `[dx, dy]` vector from `directions`, wrapping each
axis by `width`/`height` to land on `new_state`. `dindex` becomes `prev` for
the following move.

Exactly how `dindex` is computed from `(state, g, index, prev)` is not
written down here. Every raw quantity it's built from — `glyph_values`,
`mask`, `mask_shift`, `salt`, `stride`, `turn_bias`, `rotation`, `cycle` — is
already exactly what `normalize` reports for that room; what's missing is
how those combine, and that has to come from watching the game make moves,
not from this file.

The game will demonstrate single steps on request: `glyph-mill --root <dir>
probe <room> --state S --glyph G --index I [--prev P]` plays out the real
transition for exactly that `(S, G, I, P)` — `S`, `I`, and `P` don't have
to correspond to anywhere the walker has actually been, `P` defaults to
unset (first move) — and prints `{"new_state": ..., "dindex": ...,
"queries_remaining": ...}`. Demonstrations for any room, asked for by
anyone, all draw down one shared, non-renewing allowance per container;
once `queries_remaining` hits zero the game stops demonstrating for good,
so this can't stand in for knowing the movement rule at solve time — only
for working the rule out ahead of time. `play`'s `move`/`check` are a
separate, blinder protocol (glyph legality and final accept/reject only,
never an intermediate cell) and don't substitute for `probe`.

A room is accepted when, after exactly `max_moves` glyphs, the walker sits
on `target`, and every beacon's cell in `beacons` matches the walker's
position at that beacon's move-count index (index `0` is the start cell,
before any move).
