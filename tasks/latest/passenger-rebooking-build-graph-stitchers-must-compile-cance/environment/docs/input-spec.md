# Input specification

All inputs live under the dataset root (/app/data/ by default).

## passengers.json

```json
{
  "passengers": [
    {
      "passenger_id": "PAX-001",
      "name": "Example",
      "loyalty_tier": "gold",
      "fare_class": "J",
      "itinerary": [
        {
          "leg_seq": 1,
          "flight_id": "UA101",
          "carrier": "UA",
          "origin": "ORD",
          "destination": "DEN",
          "departure_utc": "2026-06-15T14:00:00Z",
          "arrival_utc": "2026-06-15T15:30:00Z",
          "fare_class": "J"
        }
      ]
    }
  ]
}
```

loyalty_tier is one of: platinum, gold, silver, none.

Top-level fare_class is the ticket fare class; each leg may repeat fare_class for that segment.

## flight-cancellations.json

```json
{
  "cancellations": [
    {
      "event_id": "CAN-001",
      "flight_id": "UA101",
      "revision": 1,
      "recorded_utc": "2026-06-14T10:00:00Z",
      "replacement_pool": [
        {"flight_id": "UA201", "carrier": "UA", "fare_class": "J"}
      ]
    }
  ]
}
```

Multiple events may reference the same flight_id with increasing revision numbers.

## seat-inventory.json

```json
{
  "flights": [
    {
      "flight_id": "UA201",
      "carrier": "UA",
      "origin": "ORD",
      "destination": "DEN",
      "departure_utc": "2026-06-15T18:00:00Z",
      "arrival_utc": "2026-06-15T19:30:00Z",
      "inventory": {"F": 0, "J": 2, "W": 4, "Y": 20}
    }
  ]
}
```

inventory keys are fare classes F, J, W, Y with non-negative seat counts.

## alliance-agreements.json

```json
{
  "carriers": {
    "UA": {"partners": ["LH", "AC"]},
    "AA": {"partners": ["BA"]}
  }
}
```

## airline-policies.json

```json
{
  "connection_protection_minutes": 45,
  "priority_weight": {
    "loyalty": {"platinum": 400, "gold": 300, "silver": 200, "none": 100},
    "fare_class": {"F": 40, "J": 30, "W": 20, "Y": 10}
  },
  "fare_class_rank": {"F": 4, "J": 3, "W": 2, "Y": 1},
  "upgrade_on_cancel": true,
  "max_fare_upgrade_steps": 1,
  "priority_pick_mode": "priority_score"
}
```

priority_pick_mode may be priority_score or manifest_passenger_order.
