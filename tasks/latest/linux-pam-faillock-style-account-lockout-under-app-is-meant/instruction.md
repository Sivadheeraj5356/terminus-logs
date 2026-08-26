Linux PAM faillock-style account lockout under `/app` is meant to stop credential stuffing and brute-force password attacks against principals. Access decisions are judged from a host management view and from a separated user-namespace privilege boundary: a principal locked out on the host must also be denied inside the namespace, and the reverse. After realistic attack traffic — burst failed logins, grace-hold expiry, out-of-order compensating unlocks, enforce suspend/resume, principal switches, truncated auth-event tails, and separate controller invocations across restarts — lockout denials, unlocked access, and failure tallies drift between those views. Namespace privilege boundaries no longer match host-side authentication enforcement, so principals locked on the host can still authenticate in the namespace (and the reverse).

Restore PAM authentication lockout integrity so host and namespace views agree on who is locked, deny paths stay consistent across privilege boundaries, and the security audit surfaces in `/app/output/lock_ledger.json` and `/app/output/lock_audit.json` reflect live auth-store enforcement rather than hand-authored JSON. The graded access-control binary is `/app/bin/bayctl`. Lockout attack scenarios live under `/app/data/scenarios/`; failed-login and unlock records live under `/app/data/batches/`. Lockout thresholds, unlock semantics, grace-hold expiry, legacy tally merge, and digest rules are defined in `/app/docs/lock_rules.md` and `/app/docs/lock_contract.md`. When starter code disagrees with those documents or this note, this note wins.

## Access-control invariants

- Failed authentication must increment the authoritative principal tally and lock when the failure limit is reached; both `host` and `ns` views must show the same `failure_count` and `locked` decision for the active principal.
- A successful unlock must clear the auth-store tally and leave both views with `locked` false and `failure_count` 0.
- Incomplete trailing auth records must not poison failure counters or unlock decisions.
- Re-applying an already-recorded attack record name is a no-op. Re-evaluating lockout enforcement twice on unchanged durable evidence must not change semantic ledger fields.
- Legacy openings at `/app/data/legacy/tally_v0.json` seed authoritative tallies on first rebuild and stay additive with later journal evidence for the same principal (do not drop a legacy opening merely because the journal later mentions that principal).

## Authentication enforcement reports

`/app/output/lock_ledger.json` is the lockout enforcement ledger: `generated_from` must be `baylock-lock-v2` and include `attempt_count`, `failure_total`, `event_line_count`, `applied_count`, `rejected_count`, `projection_digest`, `views` (each with `view_id`, `principal`, `failure_count`, `locked`), `audits` (each with `actor_ref`, `seq`), and `ledger_digest`. Both `host` and `ns` rows must appear for the active principal.

`/app/output/lock_audit.json` is the access-control audit trail: `generated_from` must be `baylock-audit-v1` and include `batch_count`, `journal_digest`, `projection_digest`, `batches`, and `audit_digest`. When ledger and audit are emitted from the same lockout enforcement state, `projection_digest` must agree.
