# Turn rules

Phases run in this order for every case. First lock. Then mix. Then open. Then settle.

## Map JSON

Each map under `/app/environment/fixtures/maps/` is a JSON object.

Required fields include width (integer), height (integer), walls as an array of
x y blocked cells, and players as an array of objects with id, start x y, and
intent x y.

Case ids and per-case epoch, salt, and weight come from
`/app/environment/fixtures/cases.toml`. grid_a means a visible geometry case.
grid_b means a visible mix case. grid_c means a visible timing-mask case.
grid_x means the held-out geometry case. grid_y means the held-out mix case.

## Slots

Each player contributes one locked cell index of the form y times width plus x
taken from that player's intent coordinate on the map (not from start, and not
from any post-collision settle position). Build a Uint32Array of those indices
in player-id order.

## Digest

Copy the slot values and sort them ascending as unsigned 32-bit integers.
Format each sorted value as an 8-digit lowercase hex string.
Join with colon characters and append hash plus the case salt formatted as
lowercase hex without zero-fill beyond natural hex digits.
SHA-256 (sha256) the UTF-8 payload. The digest is the first 16 hex characters
of the digest (lowercase).

## Mix

Start from prior (the runner always passes zero for a fresh case). For each
locked cell index in ascending sorted order, add cell times weight into prior,
then reduce that sum modulo 1000003. Use the locked intent cell indices, never
settle positions. Return the final prior.

## Certificate

Build the UTF-8 string formed by digest, then a pipe, then epoch, then a pipe,
then sorted_cells, where sorted_cells is the locked cell indices sorted
ascending and joined with commas. SHA-256 that payload. The certificate is the
first 16 hex characters (lowercase).

## Lit set

From each locked intent cell, mark every empty (non-wall) cell within Manhattan
distance at most two on the map. Union those sets. Sort ascending for output.

## Outputs

`/app/output/sheet.json` contains a cases array of objects with id, epoch,
digest, mix, cert, cells (sorted locked indices), and lit (sorted lit indices).
The field run_digest is computed as the first 16 hex chars of SHA-256 over the
concatenation of each case digest in cases-file order, joined by pipe.

`/app/output/vlog.jsonl` has one JSON object per case with fields id, epoch,
digest, cert, and cells (same values as the sheet row).

Every case id in `/app/environment/fixtures/cases.toml` must appear exactly once
in both artifacts after `npm run play`.
