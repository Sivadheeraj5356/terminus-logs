# Staging contract

Stage loads the input bundle, computes input_digest, collapses cancellations, allocates seats, and persists snapshot plus ledger. Publish reads only staged files.

Stage writes /app/state/rebooking-snapshot.json and /app/state/rebooking-ledger.json per ledger-contract.md.

## Cancellation collapse

Before allocation, collapse cancellations sharing the same flight_id. Keep the event with highest revision. On equal revision, keep the lexicographically smallest event_id.

Sort collapsed cancellations by (recorded_utc ascending, event_id ascending) for disruption_date derivation only.

## Cancelled flight set

cancelled_flights is the sorted unique list of flight_id values from collapsed cancellations.

## Passenger priority ordering

Compute priority_score per passenger as loyalty weight plus fare_class weight from airline-policies.json.

When priority_pick_mode is priority_score, sort passengers descending by priority_score, then ascending by passenger_id.

When priority_pick_mode is manifest_passenger_order, preserve passengers.json array order.

## Seat allocation pass

Initialize remaining seat inventory from seat-inventory.json (deep copy).

For each passenger in priority order, scan itinerary legs in leg_seq order. For each leg whose flight_id is in cancelled_flights:

1. Build candidate replacements from the collapsed cancellation replacement_pool for that flight_id plus any seat-inventory flight matching origin and destination of the original leg.
2. Filter candidates by alliance-rules.md using the original leg carrier.
3. Filter candidates by fare_class rank rules in airline-policies.json relative to the leg fare_class (or passenger fare_class when leg fare_class is empty). Downgrade to a lower fare class is not allowed. Same fare class is always allowed. Upgrade is allowed only when upgrade_on_cancel is true and the rank gap does not exceed max_fare_upgrade_steps.
4. Filter candidates by connection-rules.md against the next itinerary leg (if any) using arrival times after prior legs are rebooked.
5. Sort surviving candidates by flight_id ascending, then fare_class ascending. Pick the first candidate with available inventory for its fare_class.
6. Decrement inventory. Append a rebooked_leg row.

Passenger status is rebooked when every cancelled itinerary leg received a replacement; standby when any cancelled leg could not be rebooked; unaffected when no itinerary leg was cancelled.

auto_rebooked_passenger_ids lists sorted passenger IDs with status rebooked.

## Snapshot fields

| Field | Meaning |
|-------|---------|
| snapshot_version | Always 1 |
| snapshot_fingerprint | sha256 canonical JSON of the snapshot object with the snapshot_fingerprint key omitted from the hash input entirely (do not include the key with an empty string) |
| disruption_date | UTC calendar date YYYY-MM-DD of the latest recorded_utc among collapsed cancellations |
| collapsed_cancellation_count | Count after cancellation collapse |
| auto_rebooked_passenger_ids | Sorted passenger IDs with status rebooked |
| passenger_records | One row per passenger in priority processing order |
| remaining_seats | flight_id to fare_class to count; include only fare classes with count greater than zero |
| cancelled_flights | Sorted cancelled flight_id list |

Fingerprint uses sorted JSON keys, compact separators, same algorithm as export fingerprints. Excluding snapshot_fingerprint means the key is absent from the serialized object used for hashing; an empty-string value for that key is not equivalent.
