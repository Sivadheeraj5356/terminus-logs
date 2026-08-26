# Message-broker access policy

Applies to `/app/rabbitmq_definitions.json`, a simplified export of our
RabbitMQ broker's definitions:

```
{
  "users": [ {"name": "...", "tags": [...]}, ... ],
  "vhosts": [ {"name": "..."}, ... ],
  "permissions": [
    {"user": "...", "vhost": "...", "configure": "<regex>", "write": "<regex>", "read": "<regex>"},
    ...
  ]
}
```

Only the `permissions` array is graded and should change. `users` and
`vhosts` list every account and virtual host that exists; do not add,
remove, or retag entries there.

Evaluate every date-scoped rule in this document (the permission
changelog and the time-boxed incident access section) as of
**2026-07-16**, the current date.

A permission entry grants its user the named capability (`configure`
creates/deletes queues and exchanges, `write` publishes, `read`
consumes) on exactly the resources in that vhost whose name matches the
entry's regex for that capability. An empty string for a capability
means no access to that capability at all. Every vhost's resources are
named `<vhost-name-without-the-leading-slash>.<resource>`, e.g. vhost
`/billing` holds resources like `billing.invoices`.

## Tags override everything

A user tagged `administrator` has full `configure`/`write`/`read` on
every vhost, and a user tagged `monitoring` has `read` (never
`configure` or `write`) on every vhost, regardless of anything in
`permissions` for that user. A tagged user must have NO entry in
`permissions` at all: their access comes entirely from the tag, and an
explicit entry for them is redundant and must not be present.

## Tiers and their default grants

Every vhost belongs to one tier and has one owning team, stated below.
Unless a vhost is named in "Documented overrides", its only grants are
the ones this table describes, with `<team>` meaning every user whose
name is listed as that vhost's owning team.

- **confidential**: every owning-team user gets `configure`, `write`,
  and `read` all set to that vhost's prefix pattern: `^<prefix>\..*`,
  where `<prefix>` is the vhost's own name with the leading `/` dropped
  (e.g. `/billing` becomes `^billing\..*`). In addition,
  `svc-audit-collector` gets `read` (never `configure` or `write`) set
  to the same prefix pattern on every OTHER confidential vhost besides
  its own.
- **internal**: every owning-team user gets `configure`, `write`, and
  `read` all set to that vhost's prefix pattern, the same way. No one
  else gets anything.
- **public**: the owning-team user gets `configure`, `write`, and
  `read` set to that vhost's prefix pattern. Every OTHER user that does
  not hold the `administrator` or `monitoring` tag gets `read` (never
  `configure` or `write`) set the same way.

## Vhosts, tiers, and owning teams

| Vhost | Tier | Owning team |
|---|---|---|
| /billing | confidential | svc-billing-api, svc-billing-worker |
| /payments | confidential | svc-payments-gateway, svc-payments-recon |
| /audit-log | confidential | svc-audit-collector |
| /orders | internal | svc-orders-api |
| /fulfillment | internal | svc-fulfillment-worker |
| /reporting | internal | svc-reporting-etl |
| /public-status | public | svc-public-status-writer |

## Documented overrides

Only these three vhosts deviate from the tier table above, and only in
the way described for each; every other grant on these vhosts still
follows the tier table.

- **/billing**: `svc-payments-gateway`, from a different team, holds a
  narrow read-only exception for a legacy cross-team integration,
  scoped to the single EXACT resource name `billing.legacy-invoices`
  (not the whole `billing.` prefix).
- **/audit-log**: the confidential tier's "`svc-audit-collector` reads
  every other confidential vhost" rule does not extend to `/audit-log`
  itself; nobody besides the owning team has any grant here.
- **/reporting**: in addition to the owning team's grant, every user
  named in `/app/DOWNSTREAM_CONSUMERS.md` gets `read` (never
  `configure` or `write`) scoped to the `/reporting` prefix pattern.

## Permission changelog supersedes the tier table AND the overrides

`/app/PERMISSION_CHANGELOG.md` is a dated, append-only log of individual
capability changes, not necessarily listed in chronological order in the
file. For a given (user, vhost, capability) combination that has one or
more entries in the changelog, the LATEST-DATED entry (by the date
column, never by position in the file) for that exact combination is
authoritative and overrides whatever the tier table, "Documented
overrides" section, and time-boxed incident access below would otherwise
say -- including granting a capability none of those sections mention,
revoking one they grant, or revoking a grant that itself came from
"Documented overrides" (an override is not exempt from being superseded
this way). A changelog line naming a vhost that is not in the "Vhosts,
tiers, and owning teams" table above (including a near-miss misspelling
of a real vhost name) does not refer to any real vhost and has no
effect. A (user, vhost, capability) combination with no changelog entry
at all is governed purely by the tier table, overrides, and incident
access.

## Time-boxed incident access

`/app/INCIDENT_ACCESS.md` lists individual incident-response grants,
each naming a user, a vhost, and a `[start date, end date]` window
(inclusive on both ends). While the current date falls inside a grant's
window, that user gets `write` and `read` (never `configure`) set to
the named vhost's prefix pattern; outside the window (including a
window that has not started yet, or one that already ended), the grant
has no effect at all, as if the line were not there. A user can appear
in `/app/INCIDENT_ACCESS.md` more than once for different vhosts or
windows; evaluate each line independently. Incident access is a
separate mechanism from `permissions`, tags, and the changelog -- it is
never itself subject to a changelog entry, and (like tag-derived access)
it does not count toward either budget below, since it comes from a
fixed reference document rather than a `permissions` grant the agent
edits.

## Confidential-tier budgets

Two independent budgets apply to `/billing`, `/payments`, and
`/audit-log` combined, counting only grants in `permissions` --
`administrator`-tagged and incident-derived access are fixed facts, not
`permissions` grants, and are out of scope for both budgets. Never
remove a username listed in `/app/PROTECTED_SERVICE_ACCOUNTS.md` from
either capability to satisfy its budget.

- **configure budget**: at most 3 distinct usernames may hold a
  non-empty `configure` capability across the three vhosts combined.
- **write budget**: at most 4 distinct usernames may hold a non-empty
  `write` capability across the three vhosts combined. This is
  independent of the configure budget -- a user cleared by one budget is
  not automatically cleared by the other, and a user can be trimmed by
  both.

For each budget separately, if the combined distinct count for that
capability would exceed its cap, repeatedly find whichever of the three
vhosts currently has the most holders of that capability (a vhost's
count is taken after any trims already applied to it this pass for THIS
budget; ties broken by vhost name, ascending alphabetically) and clear
(set to an empty string) that capability field of the alphabetically-last
non-protected holder on that vhost, until the combined distinct count for
that capability is at its cap or no non-protected holder of that
capability remains anywhere. Clearing one capability this way never
touches that user's other capabilities on the same vhost.
