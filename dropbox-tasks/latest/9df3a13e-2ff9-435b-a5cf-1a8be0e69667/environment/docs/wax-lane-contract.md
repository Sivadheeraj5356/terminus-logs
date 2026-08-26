# Wax lane claim contract

## Goal

Allot wax lots onto shuffleboard lanes so accepted lots never share a lane, respect friction-band homogeneity, honor mutex groups, and maximise total score with a deterministic tie-break.

## Court layout

Court JSON under /app/data/rink-lanes.json:

- court_id: string
- lanes: array of { id, band, mutex_group }
- band: slow | medium | fast
- mutex_group: string label; across the accepted allotment, at most one lane from each mutex_group may be claimed

## Wax lots

Wax lot manifest under /app/data/disk-packages.json:

- lots: array of { id, lanes, score, weight }
- id: unique lot identifier
- lanes: lane id list the lot claims together (all-or-nothing package)
- score: non-negative integer welfare contribution if accepted
- weight: positive integer; informational only for ledger rolls, not a solver constraint

## Acceptance rules

1. Package integrity: every lane id in a lot must exist on the court.
2. Band homogeneity: all lanes claimed by one lot must share the same friction band. Mixed-band lots are illegal and must be rejected before search.
3. Disjoint lanes: accepted lots must use pairwise-disjoint lane sets.
4. Mutex: if two lanes share mutex_group, at most one of them may appear among all accepted lots.
5. Objective: maximise the sum of scores of accepted lots.
6. Tie-break: among optimal score sets, choose the acceptance set whose sorted lot ids joined by "," is lexicographically least.

## Claim ledger JSON

Write /app/output/wax-lane-claim-ledger.json with keys:

- schema: always "wax-lane-claim-ledger/v1"
- court_id: from court
- accepted: array of { lot_id, lanes, score, band } sorted by lot_id ascending
- rejected: array of { lot_id, reason } sorted by lot_id for lots not accepted (reason is illegal_band | collided | mutex | suboptimal)
- total_score: integer
- allot_fingerprint: lowercase hex SHA-256 of the compact string
  `court_id|` + joined accepted lot ids sorted + `|` + for each accepted lot in lot_id order `lot_id:` + lanes sorted joined by "," + `;`
- lots_digest: must equal the chalk slate lots_digest for the same run
- chalk_epoch: integer copied from the chalk slate

Reject reasons for illegal lots (band or unknown lane) use illegal_band. Lots legal for search but not selected use suboptimal if they would not collide with the chosen optimum when considered alone and collided/mutex if they share lane or mutex with an accepted lot. When multiple reasons could apply, prefer illegal_band, then collided, then mutex, then suboptimal.


## Playtest simulator notes

This board is a terminal simulation game planner for shuffleboard match wax assignment, not a generic ETL pipeline.
Bundled sample court_id is the court_id field inside /app/data/rink-lanes.json.
