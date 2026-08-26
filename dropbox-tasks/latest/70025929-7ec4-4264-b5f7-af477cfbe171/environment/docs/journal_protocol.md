# Assay journal protocol

Laboratory melt-curve observations arrive as JSONL rather than as a single
snapshot table. The certifier reconstructs the active measured temperature for
each assay and classifies it under floating-point numeric policy against the
assay uplink setpoint. Blank lines are ignored. Every other line is a JSON object.

Common event fields: `event_id` field means the stable event identity string;
`assay_id` field means the assay identity string; `seq` field means the
nonnegative logical sequence integer; `kind` field means the event kind string.
Measurement-bearing events also carry a nonnegative integer `revision` field,
finite numeric `measured_tm` and `uplink_tm` fields, and string
`instrument_run` field.

Kinds:

- `measurement` contributes an observation.
- `supersede` names `target_event_id` field means the event id removed before
  this supersede contributes its own measurement.
- `tombstone` names `target_event_id` and removes that target.
- `rollback` carries `through_seq` field means the nonnegative cutoff sequence;
  it removes earlier measurement-bearing effects whose sequence is greater than
  `through_seq` for the same assay.

Equivalent repeated event ids represent transport retries and increment the
duplicate count. Conflicting reuse of an event id with a different payload is
invalid. Logical replay sorts by `(seq, event_id)`, so a target may appear later
in the file than a reference that names it. References stay within one assay.
Measurements with a revision below the greatest already accepted revision for
that assay are stale. The active observation is the remaining measurement with
greatest `(revision, seq, event_id)`. An assay left with no active observation
is invalid.

Policy files use schema `qpcr-policy-v2`, a positive finite
`nonstress_tolerance_c`, and a unique string array `stress_assays`. Stress
assays classify measured temperature at or below uplink as `within`, and values
above uplink as `over`; strict rows report `tolerance_c` as 0. Other assays
report the configured tolerance and classify absolute delta at or below it as
`within`, and larger deltas as `outside`. Policy strings on rows are `strict`
or `band`.

## Evidence package

Output schema is `qpcr-attestation-v2`. The package has `schema`, `provenance`,
`assays`, `trace`, and `summary`.

Provenance records lowercase digests `journal_digest`, `config_digest`, and
`cache_key`. The `logical_events` field means the integer count of unique
logical events after duplicate collapse and equals the length of `trace`. The
`duplicate_events` field means the integer count of transport-retry collapses.

Assay rows are sorted by `assay_id` and record `assay_id`, `active_event_id`,
`revision`, `instrument_run`, `measured_tm`, `uplink_tm`, signed `delta_c`,
`tolerance_c`, `policy`, `classification`, and lowercase `witness`. The
`active_event_id` field means the event id of the selected active observation
for that assay.

Trace rows are sorted by `(seq, event_id)` and record `event_id`, `assay_id`,
`seq`, `kind`, `event_digest`, `occurrences`, and `effect`. The `event_digest`
field means the lowercase digest of the canonical event object. Effects are
`accepted`, `superseded`, `tombstoned`, `rolled_back`, `stale`, or `noop`.

Summary counts `assays_total`, `within_total`, `over_total`, `outside_total`,
and `trace_total`.

## Digests and cache identity

Canonical JSON recursively sorts object keys, uses compact UTF-8 JSON without
HTML escaping, preserves array order, and normalizes numbers. Digests use the
sha256 algorithm and are lowercase hexadecimal.

- Each `event_digest` is computed as the digest of the canonical event object.
- `journal_digest` is computed as the digest of newline-joined event digests in
  logical `(seq, event_id)` order after duplicate collapse.
- `config_digest` is computed as the digest of canonical policy JSON. Object
  key order in the policy file must not change the digest.
- `cache_key` is computed as the digest of the UTF-8 text:

```text
qpcr-journal-v2
<journal_digest>
<config_digest>
```

- Each row `witness` is computed as the digest of `qpcr-witness-v2`, then the
  config digest, then the ordered event digests for that assay whose effects
  are `accepted`, `superseded`, `tombstoned`, or `rolled_back`, joined with
  newlines. Witness strings are 64-character lowercase hex.

Reordering lines or repeating equivalent events must preserve assay rows,
witnesses, journal digest, and cache key apart from the documented duplicate
count and occurrences. Changing journal or policy content must select a
different content-addressed cache entry.

## Invalid input and publication

Malformed or truncated JSON, missing targets, cross-assay targets, nonfinite
values, conflicting event ids, and assays without an active observation are
invalid. Invalid input must return nonzero without changing an existing output
file and without publishing a new cache entry. Successful writes replace the
output and matching cache entry atomically. Repeated successful runs with the
same inputs are byte-identical.

## Shipped baseline

`/app/environment/data/assay_journal.jsonl` and
`/app/environment/data/assay_policy.json` are a small operational example.
Assay ids include `A17`, `B04`, `C09`, and `D12`. Event ids include
`evt-b04-new` and `evt-d12-01` among others. Stress assays in the shipped
policy are `A17` and `B04`.
