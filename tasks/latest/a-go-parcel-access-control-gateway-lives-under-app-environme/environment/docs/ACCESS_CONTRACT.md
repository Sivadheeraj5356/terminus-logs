Parcel access-control contract

The gateway reads one whitespace-separated record per line. Empty lines and lines whose first non-space token is a comment are ignored. Valid state records update in-memory state and emit no output. Valid REQ records emit exactly one line in the form request_id ALLOW route_id or request_id DENY route_id. Ignored records emit no output and must not mutate state.

Record grammar

All route ids are decimal integers from 0 through 127. All record types are field-count exact; records with missing fields, extra fields, non-numeric numeric fields, negative route ids, or out-of-range route ids are ignored.

REQ request_id route_id actor scope phase units segment_flag
PIN route_id actor scope phase units segment_flag
HOLD route_id ttl actor scope phase units segment_flag
MAP route_id source_route_id ttl
PAIR route_id left_source_route_id right_source_route_id ttl
BUDGET route_id ttl max_units
LEASE route_id ttl actor max_units
RATE route_id ttl max_allows
SEAL route_id ttl actor scope phase units segment_flag

REQ, PIN, HOLD, and SEAL require units >= 0 and segment_flag equal to 0 or 1. HOLD, MAP, PAIR, SEAL, BUDGET, LEASE, and RATE require ttl > 0. BUDGET max_units, LEASE max_units, and RATE max_allows require values >= 0.

Route policy table

For route i, compute:

actor = ROLES[i mod 8]
scope = SCOPES[(i * 3 + 1) mod 16]
phase = STATES[(i * 5 + 2) mod 8]
limit = 80 + 15 * (i mod 9)

ROLES = ops, finance, carrier, support, admin, auditor, partner, worker.
SCOPES = north, south, east, west, global, retail, wholesale, intl, archive, priority, standard, field, warehouse, cold, fragile, bulk.
STATES = draft, queued, active, settled, paused, closing, replay, audit.

Routes 0 through 47 and 80 through 127 are STRICT. They require matching actor, scope, phase, units <= limit, and segment_flag 0.

Routes 48 through 55 and 64 through 71 are SCOPE_FLEX. They require matching actor and scope, units <= limit, and segment_flag 0. Phase may vary.

Routes 56 through 63 and 72 through 79 are STATE_FLEX. They require matching actor and phase, and units <= limit. Scope may vary. If segment_flag is 1, only that request's capacity is 2 * limit. Segment_flag 0 uses the base limit. No other route mode accepts segment_flag 1.

REQ decision order

For every valid REQ, use the original requested route for all route-keyed state. An unsequenced request_id is a replay key for valid REQ records. If a previous valid REQ used the same unsequenced request_id, emit the previously stored decision and the previous original route_id, then stop processing that line. Duplicate replay does not consume or age checkpoints, leases, overlays, budgets, rates, or sequence state. Invalid REQ records never create replay entries. Valid request IDs of the form prefix:number are not replay keys because the sequenced binding contract controls their retry and rollback behavior.

For a first valid unsequenced request_id or any valid sequenced request_id, apply checks in this order:

1. Original-route checkpoint.
2. Original-route lease.
3. Original-route seal.
4. Sequenced request-id binding.
5. Overlay-resolved route policy.
6. Original-route rate quota.
7. Original-route budget.
8. Emit the decision line and age applicable ttl state.

A denial at any step still ages applicable ttl state for that valid REQ. A checkpoint, lease, seal, sequence, policy, or rate denial does not spend rate or budget capacity. A budget denial does not spend budget capacity. Rate and budget capacity checks happen before that route's ttl is aged.

Checkpoints

PIN and HOLD share one pending checkpoint slot per route. Any later valid PIN or HOLD for the same route replaces the previous checkpoint, even when the type changes.

A checkpoint compares actor, scope, phase, units, and segment_flag against the next valid REQ for that same original route. If all fields match, consume the checkpoint and continue to the later decision steps. If any field differs, consume the checkpoint, emit DENY for that REQ, age applicable ttl state, and stop that REQ.

PIN checkpoints do not expire by ttl. HOLD checkpoints expire by ttl. A valid REQ for any different route ages every pending HOLD checkpoint by one tick. Ignored records do not age HOLD checkpoints. A valid REQ for the same route that consumes or mismatches a checkpoint does not age that checkpoint before it is consumed.

Seals

SEAL is keyed by original route. A later valid SEAL for a route replaces the earlier seal. A seal compares actor, scope, phase, units, and segment_flag against every valid REQ for that same original route while the seal is active. If all fields match, the seal remains active and the request continues to sequence, overlay policy, rate, and budget checks. If any field differs, emit DENY before the sequence gate and do not spend rate or budget capacity. Seal ttl ages on every valid REQ for the original route, including the request that matched or mismatched the seal. Duplicate unsequenced replay does not age a seal.

Overlays

MAP replaces one original route's policy with one source route's policy. PAIR replaces one original route's policy with two source policies; the request is allowed by the overlay only when both resolved source policies allow the same request fields.

MAP and PAIR records share one overlay slot per route. A later valid MAP or PAIR for the same route replaces the prior overlay. Overlays are resolved after checkpoint, lease, and sequence checks. Output always prints the original requested route id.

Overlay sources may themselves have active overlays. Follow chains until a real route policy is reached. If an overlay cycle is reached, deny the REQ instead of falling back to the original route or recursing indefinitely. Consulting a source overlay through another route does not age the source overlay. Only the overlay keyed by the original route ages on a valid REQ for that original route.

Budgets, leases, and rates

BUDGET is keyed by original route. It has ttl and remaining units. Only an otherwise allowed request that reaches the budget step and has units <= remaining units spends budget capacity. Denials before the budget step do not spend budget. Denied budget checks do not spend budget. Budget ttl ages on every valid REQ for the original route, regardless of allow or deny outcome.

LEASE is keyed by original route. It permits only the configured actor and units <= max_units before sequence, overlay policy, rate, and budget are checked. A lease denial does not spend rate or budget capacity. Lease ttl ages on every valid REQ for the original route, including the denied request.

RATE is keyed by original route. It counts allowed requests, not units. Only a request that passes checkpoint, lease, sequence, and overlay policy reaches rate capacity. If remaining allows is zero, deny without spending rate or budget. If remaining allows is positive, spend one allow and continue to budget. Rate ttl ages on every valid REQ for the original route.

Sequenced request IDs

A request id without exactly one colon has no sequence marker. A marked id has prefix:number. Prefix must be non-empty. Number must be a decimal integer from 1 through 4096.

Sequence state is keyed by prefix and actor. The first accepted in-order marker for a prefix owns that prefix for its actor and must have number 1. Later marked requests using that prefix from a different actor are denied. For the same prefix and actor, each accepted marked request must use the next number exactly.

The stream is bound to the original route's mode family and 16-route sort block before overlays are resolved. The mode family is STRICT, SCOPE_FLEX, or STATE_FLEX from the original requested route. The sort block is route_id / 16 using integer division. Unexpected sequence numbers and owner drift deny without advancing the stream. If the expected next number arrives but the original route has mode-family drift or sort-block drift, deny the request but keep that sequence number consumed. These sequence denials do not spend rate or budget capacity.

Sequence state is tentative for the checks that happen after the sequence gate. If a marked request passes the sequence gate and is later denied by overlay policy, rate, or budget, roll back the new prefix claim or next-number advance for that request.
