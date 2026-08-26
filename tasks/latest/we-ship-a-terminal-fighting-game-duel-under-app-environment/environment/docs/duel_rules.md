# Fighting-game duel rules

Rulebook for a deterministic two-fighter terminal duel used by host replay and
online match play. Integer-only; no randomness or floating point.

## World

Positions are integers on a line from 0 to 9. Each fighter has position, hp,
and meter. Initial layout: player 0 at 2/100/0, player 1 at 7/100/0. Player 0
stays left of player 1.

## Inputs

Per-tick input is a bitmask: LEFT=1, RIGHT=2, ATTACK=4, BLOCK=8, SPECIAL=16.

## Tick order

Each tick runs movement then combat. Both fighters act simultaneously; player
index never grants priority.

### Movement

Per fighter: LEFT without RIGHT moves -1; RIGHT without LEFT moves +1; otherwise
0. Clamp each tentative position to [0, 9]. If tentative positions would
overlap or reverse order (new_pos0 >= new_pos1), cancel both moves.

### Combat

Use post-movement positions. dist = new_pos1 - new_pos0 (always >= 1). From the
pre-tick meter snapshot, each fighter independently:

1. SPECIAL with meter >= 10 and dist <= 3 deals 25 damage ignoring block and
   spends 10 meter.
2. Else ATTACK with dist <= 1 deals 3 if the opponent is blocking else 10, and
   gains 2 meter.
3. Else no effect.

Apply both results together. hp stays in [0, 100]; meter in [0, 20].

## Serialization

Six bytes per state: p0.pos, p0.hp, p0.meter, p1.pos, p1.hp, p1.meter.

A trajectory digest is lowercase hex SHA-256 over the initial state bytes
followed by the post-tick state bytes for every tick in order. The helper
`scripts/state_digest.py` accepts a JSON array of six-byte rows.

## Host replay

The host knows every input up front and simulates each tick with the true local
and remote bytes. `sess::run_host` is provided.

## Match tapes

`/app/environment/tapes/*.json`:

```json
{ "tape_id": "clash", "delay": 2, "inputs": [[2, 1], [4, 4]] }
```

Each `inputs[t]` is `[local, remote]`. `delay` is at least 1.

## Report schema

`bin/duel` writes `/app/output/duel_report.json`:

```json
{ "rows": [
  { "tape_id": "...", "delay": 2, "ticks": 12,
    "host_digest": "...", "pred_digest": "...", "confirmed_digest": "...",
    "rollbacks": 8, "converged": true, "final_hp": [30, 6] } ] }
```

`converged` means `confirmed_digest == host_digest`. Probe one tape with
`bin/duel --tape-file <path>` (prints one row JSON).

Online frame semantics, digest split, and worked journals: `docs/session_semantics.md`
and `docs/traces/`.
