# Connection rules

When rebooking leg N for a passenger, enforce connection protection against leg N+1 whenever leg N+1 exists:

connection_protection_minutes from airline-policies.json defines the minimum ground time between the replacement arrival of leg N and the departure of leg N+1.

Use the replacement arrival time when leg N was rebooked on this pass; otherwise use the original leg N arrival time.

Candidate replacement for leg N is rejected when:

replacement_arrival_utc plus connection_protection_minutes is strictly after leg N+1 departure_utc.

When leg N+1 is also cancelled, still evaluate connection using the original leg N+1 schedule for the window check (do not skip the check).

Times are ISO-8601 UTC strings compared lexicographically when formatted as YYYY-MM-DDTHH:MM:SSZ with fixed width fields.
