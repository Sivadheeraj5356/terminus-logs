# JWT JWKS signing-key authorization specification

This document is the normative authorization specification for JWT/JWKS
signing-key admission. Implement the admission controls under `/app/environment`
so `/app/output/freshness-report.json` is regenerated from shipped JWKS-tier
trees and the durable companion journals under `/app/output/state/<profile>/`.
All behaviour described here is exercised by the verifier as a security
admission boundary: withdrawn signing kids stay denied, stronger issuer tiers
win over weaker cache/tenant material, and foreign-realm residue does not
cross the active profile principal.

## Commands

```bash
/app/bin/mux audit --profile <name>
/app/bin/mux pulse <name>
/app/environment/cmd/mux
```

The binary is built from `/app/environment/cmd/mux` under the host tooling tree.

Profiles: `amber`, `beryl`, `onyx`. `onyx` inherits shared keys from `beryl`;
beryl durable state must already exist when onyx is audited.

## Report schema

Top level keys: `profile`, `epoch`, `counter`, `runs`, `entries`, `checkpoints`.

- **runs** — one row per run and phase: `run_id`, `phase` (`apply` or `settle`),
  `scope_digest`, `previous_digest`; sorted by `run_id` then `phase`.
- **entries** — one row per surviving key per phase: `key`, `value`, `phase`,
  `epoch`, `source_scope`, `origin`, `observed_digest`; sorted by `key`, `epoch`,
  `phase`, then the remaining string fields.
- **checkpoints** — one row per run and phase: `run_id`, `phase`, `first_seq`,
  `last_seq`, `record_count`, `epoch_floor`, `epoch_ceil`, `generation_floor`,
  `generation_ceil`, `scope_digest`; sorted by `run_id` then `phase`.

No boolean verdict fields may appear anywhere in the report document.

## Shipped JWKS-tier tree

The base source for every profile is the fixture tree under
`/app/environment/fixtures/<profile>_scopes/<tier>/`. Tiers are `issuer`
(strongest), `tenant`, and `cache` (weakest). Fixtures are applied weaker
tier first so that stronger tiers win; files inside a tier are read in
alphabetical order, and lines are read top to bottom. Each raw line is a row
operation:

- `Key=Value` — set the key
- `Key+=Value` — append `Value` as a comma-delimited token
- `Key-=Value` — remove every matching comma-delimited token
- `Key!` — delete (tombstone) the key

Blank lines and lines beginning with `#` are ignored. The shipped tree provides
the base rows; the durable journals overlay it. When no journal rows exist for a
profile, the shipped tree alone seeds the state.

## Durable companion journals

Journals live in `/app/output/state/<profile>/` and are read in this order with
these source ranks: `hold.json` (0), `hold.replay.json` (1), `hold.shadow.json`
(2), `hold.spill.json` (3), `hold.retract.json` (4). A greater source rank wins
epoch ties during canonicalization; a later read position breaks a remaining
tie. Malformed JSON in any journal is skipped and must not hide readable rows in
other journals. Rows whose `profile` field is set and does not match the active
profile are residue and are ignored.

## Canonical rows

Duplicate rows share the same `seq`, `run_id`, `phase`, `key`, and `op`. Retain
the row with the greatest `epoch`; break ties by greater source rank, then later
read order (shipped tree first, then the journals in read order).

## Generation quorum

Each profile declares a `generation_floor` in
`/app/environment/runtime/layout.json`. Rows whose `generation` is strictly below
the floor still participate in canonicalization and counter accounting but are
excluded from phase reconciliation. Rows at the floor participate in
reconciliation.

## Deferred tombstones

`delete` and `retract` rows may carry `effective_seq`. When it is omitted or
zero the tombstone applies immediately. When positive, the key remains visible
until the reconciler processes a later row in the same phase segment whose `seq`
is strictly greater than `effective_seq`; the pending tombstone activates just
before that later row is applied.

## Phase views

Within a phase segment, quorum-eligible canonical rows are processed in `seq`
order (then `key`). `set` replaces the value; `append`/`remove` edit the
comma-delimited token list of the current value; `delete`/`retract` remove the
key (subject to deferred tombstones).

**Last-touching-row metadata.** `append` and `remove` only rewrite the token
list of the prior value. After either op applies, the surviving entry takes its
`epoch`, `generation`, `mark`, `source_scope` (`scope`), and `origin` from the
row that performed that mutation — the last touching row — not from the earlier
entry those tokens came from. `set` likewise supplies those fields from the
touching row. Digests and report entry rows therefore reflect the last
touching row's metadata together with the post-edit token list.

The `settle` phase for a run starts from that run's final `apply` view and
applies the settle segment on top. For every run after the first in profile
order, the `apply` phase starts from entries carried out of the previous run's
final settle view — only entries whose `mark` is greater than or equal to `0.5`
carry forward.

## Profile inheritance

`layout.json` may declare `inherits_from` and `shared_keys` for a profile.
Before reconciling the first run's apply phase, seed the working view with each
shared key taken from the parent profile's final settle view.

## Digests

- `scope_digest`: SHA-256 over the compact JSON array of `{key, value,
  source_scope}` objects sorted by key, taken from the phase view.
- `observed_digest`: SHA-256 over the compact JSON object `{key, value, epoch,
  generation, source_scope, origin}` for each entry.

Digests are 64 lowercase hexadecimal characters. The digest chain links runs:
each run's `apply` row carries the previous run's settle `scope_digest` in
`previous_digest` (empty for the first run), and each run's `settle` row carries
that same run's apply `scope_digest`.

## Epoch, counter, and seal

`epoch` is the maximum of the layout epoch, the persisted epoch, and every
canonical row epoch. `counter` is the maximum of the layout counter, the
persisted counter, the canonical row count, the highest `generation` among
canonical rows, the persisted `seal_rev`, and the layout `seal_rev`.

A successful audit writes `/app/output/state/<profile>/epoch.json` with lowercase
keys `epoch`, `counter`, `seal_rev`, and `tag`. The `seal_rev` is at least the
layout `seal_rev`; the `tag` comes from the layout.

The pulse probe writes an advisory readiness marker at
`/app/output/state/<profile>/pulse.json` and never blocks resealing when later
journal rows carry newer evidence. It is not an admission decision.

## Spans and stability

Empty phase segments use zero sequence, epoch, and generation spans in
checkpoints. When a settle segment has no rows, the settle view still inherits
the apply view for that run. Each surviving key contributes one entry row per
phase in which it appears. Reruns must be stable across crash residue,
out-of-order journal rows, stale seals, malformed journals, foreign-profile
residue, deferred tombstone boundaries, cross-run carry, parent inheritance, and
green pulse probes. Profile run order is read from
`/app/environment/realms/<profile>.toml` using the same `runs` list the
verifier loads with tomllib. The `sha256` digest helpers must match the host
tooling implementation, not only the CLI exit status.

## Layout seed fields

`/app/environment/runtime/layout.json` declares per-profile seed fields used when
the shipped fixture tree is materialised into journal rows: `seed_epoch`,
`seed_generation`, and `seed_mark`, along with `epoch`, `counter`,
`generation_floor`, `seal_rev`, `tag`, and optional `inherits_from` /
`shared_keys`.

## Fixtures and tracked keys

Each profile ships a fixture tree under
`/app/environment/fixtures/<profile>_scopes/<tier>/`. Tracked keys carried
through the pipeline include `KidAllow`, `RotatePort`, `AuthSkew`,
`PeerKid`, `ChainDepth`, `StaleKid`, and `GraceMode`.

Profile run identifiers are the `runs` lists in
`/app/environment/realms/<profile>.toml` and include `run-a` and `run-b`.
Foreign-profile residue may carry sentinel values such as `500` or `999`; those
rows are ignored during canonicalization when their `profile` field does not
match the active profile.

Stronger tiers override weaker ones for the same key. List append and remove
edit comma-delimited tokens while the last touching row supplies epoch,
generation, mark, source_scope, and origin afterward; delete and retract
tombstones remove keys. When a profile declares `inherits_from` and
`shared_keys`, those keys are seeded from the parent profile's final settle
view before the child's first apply phase.
