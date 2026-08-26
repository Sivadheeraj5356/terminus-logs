# Export specification

Export reads /app/state/rebooking-snapshot.json and /app/state/rebooking-ledger.json only. Never reload /app/data/.

## /app/output/rebooking-plan.json

```json
{
  "plan_version": 1,
  "plan_fingerprint": "<sha256>",
  "ledger_stage_sequence": 1,
  "entries": [
    {
      "passenger_id": "PAX-001",
      "status": "rebooked",
      "priority_score": 330,
      "rebooked_legs": [],
      "rebook_rank": 1
    }
  ]
}
```

ledger_stage_sequence copies ledger stage_sequence. This field belongs in rebooking-plan.json only and must not appear in passenger-summary.json.

entries copies snapshot passenger_records in processing order with rebook_rank equal to 1-based index in that order. plan_fingerprint is sha256 of canonical JSON object {"entries": [...]} with sorted keys and compact separators.

## /app/output/passenger-summary.json

```json
{
  "summary_version": 1,
  "disruption_date": "2026-06-14",
  "total_passengers": 3,
  "rebooked_count": 2,
  "standby_count": 0,
  "unaffected_count": 1,
  "priority_pick_mode": "priority_score",
  "cancelled_flight_list": ["UA101"]
}
```

disruption_date copies snapshot disruption_date.

total_passengers is len(passenger_records). rebooked_count, standby_count, unaffected_count count statuses in snapshot passenger_records.

cancelled_flight_list copies snapshot cancelled_flights.

priority_pick_mode copies ledger priority_pick_mode.

Export must be deterministic and byte-identical on repeated export of the same snapshot and ledger pair.
