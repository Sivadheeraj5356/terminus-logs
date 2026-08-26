# License-seat allocation contract

`node /app/bin/seat-allocate <feed.ndjson> <output.json>` reads a feed of seat requests, suspensions, restores, and cancels from the first argument and writes a JSON allocation report to the second argument. The CLI must create the output directory when it is missing. It always loads `/app/data/seat_inventory.json`, `/app/data/entitlements.json`, and `/app/data/station_config.json`, even when the feed path is custom.

## Feed events

Every line is one JSON event with `id` and `type`. A `request` row has `requestId`, `edition`, an integer `seatsNeeded`, and optionally `tier` and an integer `priority` (missing priority is `0`). A `suspend` row has `seatId` and `reason` and takes the named seat out of allocation. A `restore` row has `suspendId` naming an earlier suspend event id and lifts exactly that suspension. A `cancel` row has `target` naming an earlier request or cancel event id and cancels its target.

The whole feed settles before any seat is assigned. First resolve cancels to a fixpoint: an active cancel cancels its target, and a cancel can cancel another cancel — when that happens the earlier cancel stops cancelling its own target and that target comes back. Keep recomputing until nothing changes, and in each pass only cancels that are themselves currently active count as cancellers. With `e11` cancelling request `R-7` and `e13` cancelling `e11`, the request stands; adding a third cancel on `e13` cancels the request again. A cancel whose `target` names neither a request nor a cancel event changes nothing. A cancelled request takes no part in allocation no matter where its cancel sits in the feed.

Suspensions settle next, in feed order. A suspension is active unless a later restore names its event id; a seat with more than one suspension stays out until every one of its suspensions is restored. A restore whose `suspendId` does not name an active suspension changes nothing.

## Usable seats

A seat is usable when it is in the inventory, is not suspended after the feed settles, and its `coveredThrough` is strictly after the station `allocationDate` (date strings compare as calendar dates). A seat whose `coveredThrough` equals the allocation date has expired for this batch.

A seat can be fitted to a request when the seat's `edition` appears in the `entitlement` list for the request's `edition`. A request may carry `activeUntil`, the date the seat must still be covered through; a seat whose `coveredThrough` is not strictly after `activeUntil` cannot be fitted to that request, even though it stays usable for other requests. A request with no `activeUntil` accepts any usable seat its edition allows. When the request's `tier` is listed in the station `exactEditionTiers`, only seats whose `edition` equals the request's `edition` exactly can be fitted. A request whose `edition` has no entry in `entitlement` is rejected with `reason: "unknown-edition"`. A suspend naming a seat that is not in the inventory is rejected with `reason: "unknown-seat"`.

## Filling requests

A request is filled only when it receives exactly `seatsNeeded` distinct usable seats it can accept; there are no partial fills, and a seat goes whole to one request. The batch fills the requests it can. Between candidate allocation plans, prefer the plan that fills more requests; among those, prefer the larger sum of `priority` over the filled requests; among those, prefer the plan whose set of filled requests comes earliest in feed order; among those, prefer the plan whose fitted seats, listed by `coveredThrough` then `seatId`, read earliest; among those, walk the requests in feed order and prefer the plan whose sorted seat ids for that request read earliest.

### Reservation case

Suppose the only usable seats are `S-101` (`E-CORE`, coverage ends 2027-02-18) and `S-102` (`E-TEAM-P`, coverage ends 2027-03-02), and the feed asks for one `E-TEAM-P` seat first and one `E-DATA` seat later. The earliest-covering seat `S-101` reads like the natural pick for the `E-TEAM-P` request, but it is the only seat an `E-DATA` request can receive. The batch fits `S-102` to the `E-TEAM-P` request and `S-101` to the `E-DATA` request, and both are filled. Fitting `S-101` first would leave the `E-DATA` request with nothing it can accept.

### Priority case

Suppose one usable `E-CORE` seat remains and two `E-CORE` requests want one seat each: the earlier one with no priority, the later one with `priority: 3`. Either plan fills one request, so the priority sum decides and the later request is filled. When the priorities also tie, the earlier request in feed order is filled.

### Whole-demand case

A request with `seatsNeeded: 2` and only one usable seat it can accept is unfilled, and that seat stays free for other requests or ends up unused.

## Report shape

```json
{
  "events": [],
  "allocations": [],
  "unusedSeats": [],
  "summary": {}
}
```

The report top level contains exactly four keys: `events`, `allocations`, `unusedSeats`, and `summary`, in this order. Do not add any other top-level key.

`events` lists one row per feed line, in input order. Every row starts with `id`, `type`, and `decision`. Decision strings are `request-accepted`, `cancelled`, `rejected`, `suspend-applied`, `restore-applied`, `restore-ignored`, `cancel-applied`, and `cancel-ignored`. Accepted request rows carry `requestId` and `edition`. Cancelled rows — request or cancel — carry `cancelledBy`, the sorted ids of the active cancels pointing at them, and nothing else beyond `id`, `type`, and `decision`. Rejected request rows carry `requestId` and `reason`; rejected suspend rows carry `seatId` and `reason`. Applied suspend rows carry `seatId`; restore rows carry `suspendId`, and an ignored restore adds `reason: "no-active-suspension"`. Applied cancel rows carry `target`; an ignored cancel adds `reason: "invalid-target"`.

`allocations` lists one entry per filled request, in request feed order. Each entry has `requestId`, `edition`, and `seatIds`, the fitted seat ids sorted ascending. An unfilled request does not appear in `allocations`. `unusedSeats` is the sorted list of usable seat ids that were not fitted to any request; suspended and expired seats are not usable and never appear there.

`summary` keys are alphabetized and every value is an integer:

```json
{
  "allocatedSeats": 0,
  "cancelledRequests": 0,
  "expiredSeats": 0,
  "filledRequests": 0,
  "prioritySum": 0,
  "rejectedEvents": 0,
  "requestCount": 0,
  "suspendedSeats": 0,
  "totalEvents": 0,
  "unfilledRequests": 0,
  "usableSeats": 0
}
```

`requestCount` counts accepted request rows; cancelled and rejected requests do not count. `cancelledRequests` counts request rows with decision `cancelled`; a cancelled cancel does not count. `prioritySum` sums `priority` over filled requests only. `suspendedSeats` counts inventory seats still suspended after the feed settles, `expiredSeats` counts inventory seats expired for this batch, and `usableSeats` counts seats that were usable when allocation began. `rejectedEvents` counts rows with decision `rejected`.

## Public exports

- `license/parse.js` exports `readFeed(text)` and `parseLine(line)`.
- `license/entitlement.js` exports `eligibleSeats(request, seats, rules, config)`, the usable seats the request can accept, in inventory order.
- `license/allocate.js` exports `planAllocation(events, inventory, rules, config)`, returning the report object.
