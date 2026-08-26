# DNS Publication Policy

`zone-publisher` builds a candidate zone from the snapshot and active journal records,
then evaluates publication predicates against freeze windows and scoped exceptions.

## Constants

SOA serial is a 32-bit unsigned value.
A serial is considered advanced when RFC-style serial arithmetic says the candidate
serial is greater than the original serial.
At most 2147483647 serial steps may be advanced at once.
Exactly one SOA record must exist at the zone apex.
A zone apex must not have a CNAME record.
A CNAME owner must not have any other non-DNSSEC record type.
DNSSEC side records allowed beside CNAME are RRSIG and NSEC only.
Delegation record type is NS below the zone apex.
In-zone glue is required when a delegated child nameserver name is inside that
delegated child.
Wildcard records must not be treated as covering names below a delegated child zone
cut.
TXT canonical value keeps quoted chunks but normalizes outside whitespace to one
space.

## Candidate construction

The candidate zone is built by applying active journal records to the original zone.
Active records are the surviving change set after same-`change_id` sequence selection
and higher-sequence corrections. Application order for the surviving set is sorted by
`change_id` ascending so input row order cannot change semantics.

A delete action targeting a record absent from the current candidate zone produces
`UNKNOWN_DELETE`.
A replace action deletes existing records with the same owner and record type before
adding the replacement.

The zone apex is the `zone` value used by active journal records and freeze/exception
rows. All active journal rows in a batch share that apex zone name.

## SOA and apex rules

The final candidate must contain exactly one SOA at the apex.
The candidate SOA serial must be advanced from the original apex SOA serial by
RFC-style 32-bit serial arithmetic.
Normal integer comparison is not sufficient for serial advancement when serials wrap.
When the candidate serial is not advanced, or when the forward distance exceeds
2147483647 steps, emit `SERIAL_NOT_ADVANCED`.
When the apex SOA count is not exactly one, emit `SOA_COUNT`.
An apex CNAME produces `APEX_CNAME`.

## Record exclusivity and TTL

A CNAME owner with another non-DNSSEC record type produces `CNAME_CONFLICT`.
A TTL outside 30 through 86400 produces `TTL_OUT_OF_RANGE`.
TXT rdata that is not already in canonical form produces `TXT_CANONICAL`. Canonical
form keeps quoted chunks intact and collapses any outside whitespace runs to a single
ASCII space with no leading or trailing outside whitespace.

## Delegation, glue, and wildcards

A delegation exists at any non-apex owner with NS records.
Glue is required only when a delegated child’s nameserver name is inside that
delegated child. In-zone glue means at least one A or AAAA record exists at that
nameserver owner in the candidate zone.
Missing required in-zone glue produces `DELEGATION_GLUE_MISSING`.
The finding `owner` is the delegation owner where the NS record lives, `record_type` is
`NS`, and the evidence detail names the missing glue nameserver owner.
Wildcard records whose owner lies at or below a delegated child zone cut produce
`WILDCARD_BELOW_DELEGATION`. The finding `owner` is the wildcard RR owner,
`record_type` is that RR's actual type (for example `A` or `AAAA`), not `*`. Parent
wildcards must not be treated as synthesizing answers under those cuts either; only
literal wildcard owners under a cut are reported.

## Freeze windows and exceptions

A freeze window produces `FREEZE_WINDOW` only when the active change’s zone, owner
suffix, record type, and effective UTC time overlap the freeze row. Overlap means
`start_utc <= effective_utc <= end_utc`.
An exception suppresses only the matching finding code for the matching zone, owner
suffix, record type, and overlapping UTC window. For freeze findings the overlapping
window is the active change `effective_utc`. For other findings the window check uses
the same `effective_utc` carried on the active change that introduced or last mutated
the owner and record type, or the earliest active change `effective_utc` when no single
row owns the predicate.
Exceptions do not suppress fatal input errors.

Blocking findings appear in `findings`.
Suppressed findings appear in `suppressed` and must include the suppressing exception
id.

Severity for every reported or suppressed finding is the string `blocking`.
