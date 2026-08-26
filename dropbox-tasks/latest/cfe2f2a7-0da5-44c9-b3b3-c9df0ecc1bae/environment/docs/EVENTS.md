# Event grammar

Each nonblank NDJSON line is a JSON object.

Required common fields:

- `seq`: integer, non-negative
- `epoch`: integer, non-negative
- `kind`: string

Optional common fields:

- `source`: string, default lane name or `"main"` in single-journal mode
- `rev`: integer revision, default `0`
- `cancel`: boolean tombstone flag, default `false`
- `op_id`: stable operation identifier; default is `epoch:seq:source:lane`

Supported `kind` values:

- `link_open`, `link_close`, `hop`, `quarantine`, `clear_quarantine`
- `checkpoint`, `policy_update`, `note`

Kind-specific fields:

- Lifecycle and hop events use `link` as `src>dst`.
- `hop` uses integer `ms` latency, `ms >= 0`.
- `checkpoint` uses nonempty string `tag`.
- `policy_update` uses `policy` object with the same schema as a policy file.
- `note` is valid and audited, but does not affect link state.

Malformed lines, unknown kinds, negative latency, missing required fields, invalid policy records, and invalid checkpoint snapshots must fail the run with exit code `2` and atomic output cleanup.

## Record identity and revision

Identity key is `(epoch, seq, source, op_id)`.

For the same identity key, keep only the highest `rev`. If two records share the highest `rev`, keep the one that appears later after lane merge ordering.

If the winning record has `cancel: true`, audit it as `cancelled` and do not apply it to link state. Cancelled records count in audit totals but not `applied_events`. Lower revisions are audited as `superseded`. Exact raw duplicate lines after the winner are audited as `duplicate_raw`.

Deduplication and revision selection happen before checkpoint replay, but checkpoint cursors must still make resumed replay byte-identical.

## Lane merge order

For parsed records, merge order is:

1. ascending `epoch` (numeric, not lexicographic)
2. ascending `seq`
3. ascending kind precedence: `checkpoint`, `policy_update`, `quarantine`, `clear_quarantine`, `link_close`, `hop`, `link_open`, `note`
4. ascending lane `priority`
5. ascending lane `name`
6. ascending zero-based line number within lane
7. ascending raw-line SHA-256 hex

## Link replay

- A link row exists once any non-cancelled event references it.
- `link_open` sets `open = true`.
- `link_close` sets `open = false`; repeated close is valid and audited as `noop_close`.
- `quarantine` sets `quarantined = true`.
- `clear_quarantine` sets `quarantined = false`; repeated clear is valid and audited as `noop_clear_quarantine`.
- `hop` applies only when the link is open and not quarantined.
- Suppressed hops are audited with reason `closed` or `quarantined`.
- Histogram bucket index is `min(ms / 50, 5)` (six buckets: `[0-49, 50-99, 100-149, 150-199, 200-249, >=250]`).
- `open_link_count` counts links where `open` is true at the end.
- `quarantined_count` counts links where `quarantined` is true at the end.
