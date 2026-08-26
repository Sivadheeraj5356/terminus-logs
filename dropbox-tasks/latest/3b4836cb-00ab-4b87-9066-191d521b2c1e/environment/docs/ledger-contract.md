# Ledger contract

Stage writes /app/state/rebooking-ledger.json alongside the snapshot.

```json
{
  "ledger_version": 1,
  "input_digest": "<sha256>",
  "stage_sequence": 1,
  "priority_pick_mode": "priority_score",
  "remaining_seat_map": {
    "UA201": {"J": 1, "Y": 5}
  }
}
```

input_digest is sha256 canonical JSON of the loaded input bundle (passengers, cancellations, flights, alliances, policy) with sorted keys.

stage_sequence starts at 1 when no prior ledger exists. When input_digest changes after a successful stage run, stage_sequence increments by 1 from the previous ledger value. When input_digest is unchanged, stage_sequence stays the same across repeated stage runs.

priority_pick_mode copies airline-policies.json priority_pick_mode.

remaining_seat_map mirrors snapshot remaining_seats after allocation.

Export copies stage_sequence into ledger_stage_sequence in /app/output/rebooking-plan.json only. passenger-summary.json must not include ledger_stage_sequence.
