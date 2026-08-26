# Audit schema

`audit.jsonl` contains one JSON object per decision, deterministic order, trailing newline on each line.

Required fields:

- `decision`: `applied`, `superseded`, `cancelled`, `duplicate_raw`, `suppressed`, `noop`, `checkpoint`, `policy_update`, or `note`
- `epoch`, `seq`, `lane`, `source`, `op_id`, `rev`, `kind`, `reason`, `link`

The `reason` field uses these literal values for existing decisions: `lower_rev` or `tie_break` for superseded records, `exact_raw_duplicate` for duplicate raw records, `tombstone` for cancellations, `ignored` for notes, `applied` for policy updates, the checkpoint tag string for checkpoints, `open`, `close`, `quarantine`, `clear`, or `hop` for applied link decisions, `noop_close` or `noop_clear_quarantine` for no-op lifecycle decisions, and `closed` or `quarantined` for suppressed hops.

Audit records follow actual replay decision order.
