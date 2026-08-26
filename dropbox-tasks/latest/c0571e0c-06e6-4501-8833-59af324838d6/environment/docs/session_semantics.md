# Online match session semantics

How delayed remote inputs drive a predicting fighting-game client. Fight physics
live in `duel_rules.md`; this document covers frames, digests, and resimulation.

## Roles

- Host: offline replay with every input known (provided).
- Client: player 0 sees local inputs immediately; remote bytes arrive late.

## Frames and confirmation

A tape has N ticks. Real frames index from 0 through N + delay - 1 during play,
then a flush pass runs frames N .. N + delay - 1 without advancing new ticks.

At real frame f the client may learn the true remote byte for tick r = f - delay
when 0 <= r < N and r < f.

## Client state

The client keeps:

- saved[0..=N]: authoritative snapshots after each tick (saved[0] initial).
- first_remote[0..N-1]: remote byte currently associated with each tick. It is
  set when the tick is first advanced, and rewritten for ticks in a
  resimulation range; it is not a frozen first-pass-only value.
- first_display[0..N-1]: state shown the first time each tick was simulated
  (frozen; never rewritten on resimulation).
- confirmed: highest tick whose true remote byte is known (start -1).
- rollbacks: count of resimulation events (start 0).

## Remote byte before confirmation

`guess::remote_for_tick` chooses the remote byte for tick k using only ticks
already confirmed and the tape read so far. After tick k is confirmed, every
later resimulation at or before k must use the tape's true remote byte for k.

Worked frame journals under `docs/traces/` are normative examples for the graded
behavior. They show which tick confirms at each frame and which remote byte the
client used.

## Resimulation

When frame f confirms tick r and `first_remote[r]` differs from the tape's
remote byte at r, increment rollbacks and resimulate from saved[r] forward
through the current upper bound. For each tick k in that range, rewrite
`first_remote[k]` to the remote byte used on this pass and rewrite `saved[k+1]`.
Do not rewrite `first_display` entries.

## Digest outputs

- confirmed_digest: digest over initial state then saved[1..N] after the flush.
- pred_digest: digest over initial state then first_display[0..N-1] (the on-screen
  path, kept even when later rollbacks fix saved snapshots).

## Graduation

After the flush, confirmed_digest must equal the host trajectory digest.
pred_digest generally differs whenever resimulation occurred.
