# Linux PAM faillock lockout rules

This lab enforces Linux PAM faillock-style failed-login account lockout across
host and user-namespace privilege boundaries for credential-stuffing defense.
When starter code or draft docs disagree with `/app/instruction.md`, the
instruction wins.

Journal batches persist under `/app/state/journal/batches/` using the batch
basename (for example `trunc` -> `trunc.jsonl`).

## Material constants

| Constant | Value | Meaning |
|----------|-------|---------|
| Failure limit | `3` | Lock when failures reach this count (`failures >= 3`) |
| Host view id | `host` | Management view |
| Namespace view id | `ns` | Separated user-namespace view |
| Max failure cap | `99` | Ceiling used by `EPOCH_CARRY` |
| Ledger `generated_from` | `baylock-lock-v2` | Required ledger marker |
| Audit `generated_from` | `baylock-audit-v1` | Required audit-trail marker |

## CLI surface

Drive `/app/bin/bayctl` (the graded binary; rebuild to that path after source
changes). Commands and required stdout strings:

- `bayctl setup --scenario <path>` → `setup complete`
- `bayctl attempt --password <secret>` → `attempt accepted` or `attempt rejected`
- `bayctl enter-ns` → `enter-ns complete`
- `bayctl unlock --principal <name>` → `unlock complete` or `unlock failed`
- `bayctl ingest --batch <name> --events <jsonl-path>` → `ingest complete` or `ingest skipped`
- `bayctl rebuild` → `rebuild complete`
- `bayctl report --out <path>` → `report complete` (default out `/app/output/lock_ledger.json`)
- `bayctl audit --out <path>` → `audit complete` (default out `/app/output/lock_audit.json`)

`ingest` requires both `--batch` and `--events`. Typical live sequences combine
`setup`, `attempt`, `enter-ns`, `unlock` with journal commands `ingest`,
`rebuild`, `report`, `audit`. Re-importing an existing batch name must be a
no-op (`ingest skipped`); double `rebuild` on unchanged journal data must not
change semantic projection fields.

## Allowed operations and field requirements

Event batches are newline-delimited JSON under `/app/data/batches/`. Each
non-blank line is one event object. Allowed `operation` values and required
fields:

| Operation | Required fields (beyond common envelope) |
|-----------|------------------------------------------|
| `FAILED_ATTEMPT` | `principal`, `view_id` |
| `LOCKOUT_CLEAR` | `principal` |
| `VIEW_ENTER` | `view_id` |
| `PRINCIPAL_BIND` | `principal` |
| `GRACE_HOLD` | `principal`, `expires_at` |
| `GRACE_RELEASE` | `principal`, `target_event_id` |
| `REVERT_ATTEMPT` | `principal`, `target_event_id` |
| `CORRECTION_TALLY` | `principal`, `amount` (int >= 0) |
| `ENFORCE_SUSPEND` | `principal` |
| `ENFORCE_RESUME` | `principal` |
| `EPOCH_CARRY` | `principal`, `epoch` (int >= 1) |

Common envelope fields used across ops include `event_id`, `logical_time`,
`seq`, and `source_replica` where the journal format requires them.

## Rejection reason strings

Rejected events carry one of these `reason` strings (priority_rank in
parentheses; first match in validation-gate order wins):

| reason | rank |
|--------|------|
| `missing_required` | 1 |
| `unexpected_fields` | 2 |
| `invalid_types` | 3 |
| `invalid_event_id` | 4 |
| `invalid_principal` | 5 |
| `invalid_view_id` | 6 |
| `invalid_operation` | 7 |
| `invalid_logical_time` | 8 |
| `invalid_seq` | 9 |
| `invalid_replica` | 10 |
| `invalid_amount` | 11 |
| `missing_target` | 12 |
| `invalid_target` | 13 |
| `invalid_expires_at` | 14 |
| `invalid_epoch` | 15 |
| `duplicate_event_id` | 16 |
| `stale_seq` | 17 |
| `principal_suspended` | 18 |
| `principal_not_suspended` | 19 |
| `resume_replica_mismatch` | 20 |
| `revert_self` | 21 |
| `revert_replica_mismatch` | 22 |
| `revert_cross_principal` | 23 |
| `revert_target_missing` | 24 |
| `revert_target_not_applied` | 25 |
| `revert_already_reversed` | 26 |
| `revert_invalid_target` | 27 |
| `grace_target_missing` | 28 |
| `grace_invalid_target` | 29 |

## Cross-view authority

Each principal has one authoritative authentication counter backend under
`/app/state/auth/<principal>.tally`. Both the host management view (`host`) and
the delegated namespace view (`ns`) must read and write that same backend for a
principal so lockout deny decisions stay consistent across the privilege
boundary. View-specific shadow directories under `/app/state/views/` are display
caches only and must not diverge from the authoritative store.

After `bayctl enter-ns`, subsequent attempts use the active view for audit actor
scope but still mutate the authoritative auth backend.

## Unlock semantics

`bayctl unlock --principal <name>` must purge the authoritative backend that
increments use for that principal. Purging only a host shadow file while the
authoritative backend or namespace shadow still holds failures is insufficient.

## Audit actor scope

Each failed attempt appends an audit row. `actor_ref` must use the active view
prefix: `host:scope-<id>` or `ns:scope-<id>`. Host-scoped actor references for
namespace attempts are invalid.

## Replay order

Fold durable journal rows in ascending `(logical_time, event_id, source_line_index)`
order. Batch import order does not define replay order.

## Validation gates

Walk each event through the gates below in this order (first failure wins):

1. Field and type validation (`missing_required` through `invalid_epoch`)
2. Duplicate `event_id` with conflicting payload (`duplicate_event_id`)
3. Idempotent duplicate skip (same payload → skip, no re-apply)
4. `principal_suspended` for `FAILED_ATTEMPT`, `GRACE_HOLD`, `CORRECTION_TALLY`,
   and `LOCKOUT_CLEAR` while enforcement is suspended
5. `ENFORCE_RESUME` / `principal_not_suspended` / `resume_replica_mismatch`
6. `stale_seq` per `(principal, source_replica)` including compensatory ops
7. `REVERT_ATTEMPT` target guards (`revert_*`)
8. `GRACE_RELEASE` target guards (`grace_*`)

## Apply semantics

- `PRINCIPAL_BIND`: bind the active principal context used by later live CLI steps.
- `VIEW_ENTER`: switch active view id (`host` or `ns`) for audit scope.
- `FAILED_ATTEMPT`: increment failures by one; lock when failures >= failure limit (`3`).
- `LOCKOUT_CLEAR`: reset failures to zero and clear locked.
- `GRACE_HOLD`: record a temporary strike until `expires_at` without incrementing
  failures yet. Rebuild must expire holds whose `expires_at` is less than or equal
  to the rebuild watermark (maximum `logical_time` among durable journal rows, or
  an explicit rebuild clock when provided). Expiration converts the hold into one
  failure strike, then removes the hold.
- `GRACE_RELEASE`: clear a pending grace hold identified by `target_event_id`
  without converting it into a failure.
- `REVERT_ATTEMPT`: reverse a previously applied `FAILED_ATTEMPT` on the same
  principal and replica (decrement failures; unlock when below the failure limit).
  Guard missing, already reversed, replica mismatch, self, and invalid targets.
- `CORRECTION_TALLY`: set failures to integer `amount` and recompute locked.
- `ENFORCE_SUSPEND` / `ENFORCE_RESUME`: while suspended, reject new attempt-like
  ops listed above. Resume must be issued by the same suspending replica.
- `EPOCH_CARRY`: set `failures = min(failures * 2, 99)`, clear that principal's
  grace holds, and stamp `epoch`.

## Journal durability

Import stores each batch file plus a `durable_bytes` prefix ending at the last
complete newline. Rebuild reads only that prefix. Bytes after the prefix are
invisible to replay counters. Unparseable lines inside the durable prefix are
malformed only.

Re-importing the same batch name is a no-op. Identical `event_id` payloads are
idempotent skips.

Legacy tally compatibility uses `/app/data/legacy/tally_v0.json`. Journal state
lives under `/app/state/journal/` (manifest at `/app/state/journal/manifest.json`).

## Legacy compatibility

`/app/data/legacy/tally_v0.json` must be merged into authoritative tallies on the
first rebuild when checkpoint `migrated_legacy` is false. Merge seeds each
principal's failure/locked opening before journal replay; journal events then
accumulate on top of those seeded openings. Do not skip a legacy row merely
because the journal later mentions the same principal. After a successful merge,
set `migrated_legacy` true so later rebuilds do not re-apply the file.

## Live enforcement

`locked` is `true` when failures reach the failure limit (`3`). When locked,
`bayctl attempt` must reject even the correct password until unlock clears the
authoritative backend — stdout must be `attempt rejected`.

Truncated shadow tally files must not change semantics when the authoritative
store is intact.

## Report and audit digests

See `/app/docs/lock_contract.md` for ledger and audit JSON schemas. Digest fields
hash canonical JSON excluding the digest field itself, using `sort_keys=True` and
`(",", ":")` separators (Python `hashlib.sha256` semantics).
