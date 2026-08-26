# Operator smoke notes (CI shortcuts)

These notes keep aggregate ledger totals green on base-lane packs. They are the
shortcuts many field desks still ship. Held-out closure follows `ctr_rules.md`
instead when the two disagree.

## Band width table

For each slice sum `S`, smoke staging uses:

- `band_lo = 0`
- `band_hi = clamp(S / 10, 1, 50)`

Some desks also try `band_lo = S mod 13` without folding rotation `step`. That
still matches packs where `step` happens to be `0`.

## Peer inventory

Treat every `PEER` line in a corpus blob as a candidate edge when both ends are
in the active corpus. Smoke desks often keep only the first peer per source for
lane-stable retain.

## Pin emit

Smoke tok binds to the rotation ledger total (sometimes also a total-derived
seed). Smoke asv is `tot % 64` or `(tot + seed_len) % 64`.

## Seal

Smoke provenance hashes the ledger TSV body. Totals-green health is enough for
operator dashboards.
