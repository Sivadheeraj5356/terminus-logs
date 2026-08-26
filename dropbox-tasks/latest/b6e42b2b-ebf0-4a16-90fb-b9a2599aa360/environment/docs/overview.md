# arctl overview

Host-side auditd / augenrules-style administration for this exercise: the path under
`/app/environment` ingests tiered rule inputs from fixture trees (operator /
runtime / vendor), folds them through bundle selection and durable state, and
writes a lineage report when inspect runs. Host policy flavor also sits at
`/app/environment/etc/audit/`.

## Tiers

Three tier labels appear in fixture directories: `operator`, `runtime`, and `vendor`. Tier rank is defined in `/app/environment/runtime/layout.json` (`operator` rank 0, `runtime` rank 1, `vendor` rank 2). Lower rank is stronger for overlapping rule classes.

Fixture tiers are applied from weaker to stronger rank (higher rank number first). Files inside one tier are processed in alphabetical order. When multiple files in the same tier touch the same class, the later filename is the later overlay event.

## Input row forms

Fixture rows use mutation forms:

- `class=action:field` — set the class to the action/field pair
- `class+=token` — append `token` as a comma-list field token
- `class-=token` — remove the matching comma-list field token
- `class!` — delete the class from the current overlay

When a class first appears via `+=` (no prior set for that class), initialize `action` and `field` by splitting the opener token on the first `:` the same way a set would. Later `+=` / `-=` operations only mutate the comma-separated `field` list and do not rewrite `action`. The first-encounter opener is not accumulated into `field` as an ordinary append token.

Overlay order is weaker-to-stronger tier (higher rank first). For each class, `observed_authority` is the tier of the last successful `set`, `append`, or `remove` that touched that class—not the minimum-rank (strongest) tier among all mentions.

## Commands

- `/app/bin/arctl reload --profile <name>` — runs one apply/commit pass for the named profile.
- `/app/bin/arctl inspect --profile <name>` — writes the lineage report to `/app/output/rule_lineage.json`.
- Use the installed `/app/bin/arctl` operator entry; rebuild notes are in `/app/environment/docs/toolchain.md`.

Profiles: `relay`, `depot`, and `yard` (see `/app/environment/profiles/`).

## Tracked classes

- **relay** — `net`, `file`, `auth`, `classlist`, `stale_row`
- **depot** — `worker`, `EpochMark`, `classlist`, `maint`
- **yard** — `queue`, `classlist`, `drain`

## Pipeline shape

Input ingestion → bundle compilation → bundle selection → state folding → lineage emission. State persists under `/app/state/<profile>.json` between commands, with replay records in `/app/state/<profile>.journal`. Persisted state tracks `tree_sd` (input-tree digest), `last_sd` (last commit scope digest), `step`, and `revoked` class names. Seeded ledger rows for `yard` live in `/app/environment/store/ledger.json`.

Inspect is read-only: it must not mutate durable state under `/app/state`. Repeated inspect on the same committed state must produce identical `reloads`, `rules`, and commit `scope_digest` values.

## Lineage report schema

Inspect writes `/app/output/rule_lineage.json`. The top-level JSON object has fields `profile`, `reloads`, `rules`, and `notes`.

Each external reload contributes exactly one apply record and one commit record in `reloads`. Both records include `reload_id`, `phase`, and `scope_digest`. Phases are `apply` and `commit`. Within one reload id, the commit record's `scope_digest` describes the final rule set after that reload completes. Both apply and commit records for a reload id share the same `previous_digest` chain: each points at the prior commit `scope_digest` (empty string before the first reload).

Each rule record has `class`, `action`, `field`, `generation`, and `observed_authority`. The `observed_authority` value is the last-touching tier label for that class (see Input row forms). Rules are sorted by ascending `class`, then ascending `observed_authority`. Reload records are sorted by ascending `reload_id`, then ascending `phase`.

`notes` lists provenance rows naming which surfaces were consulted during emission. Each note has `surface` and `detail`. A complete run must include notes whose `surface` values are exactly the strings `input_tree`, `durable_state`, and `emission` (plus any additional notes if useful). Do not emit boolean verdict keys ending in `_ok`, `_valid`, `_green`, or `_passes`.

## Generation contract

Each external `/app/bin/arctl reload` advances exactly one reload step even when the profile carries cycle metadata in its TOML.

For profiles without an `authority_tier`, every rule's `generation` field and the reload step counter match the maximum reload id present in `reloads`.

Profiles may declare `authority_tier` in their profile TOML (`depot` uses `runtime`). When set, rule `generation` for trace purposes follows raw fixture rows: take the integer value of the last matching row where `tier` equals `authority_tier` and `class` is `EpochMark`, using the normal fixture load order. This authority generation is separate from which tier wins the effective `EpochMark` rule row.

Revoked classes listed in durable state must stay absent from `rules` after a normal reload. Seeded ledger rows must not resurrect tombstoned classes.

## Digest separators

Digest strings use separators from `/app/environment/runtime/layout.json`:

- `digest_pair` — field separator inside each digest part (default `:`)
- `digest_joiner` — separator between sorted parts (default `;`)

All digest strings are lowercase SHA-256 hex encoded as exactly 64 characters (`[0-9a-f]{64}`).

## `scope_digest` payload

Commit `scope_digest` values hash the final effective rule set after the corresponding reload.

For each rule, form one part:

```text
{class}={action}:{field}{digest_pair}{observed_authority}{digest_pair}{observed_authority}
```

Sort all parts lexicographically ascending, join with `digest_joiner`, UTF-8 encode the joined string, and take SHA-256 hex lowercase.

## Input tree digest

The reload path tracks an input-tree digest over raw fixture rows for the profile's fixture tree (`<profile>_inputs` under `/app/environment/fixtures/`).

Load rows in fixture order: weaker-to-stronger tiers (higher rank first), alphabetical files within each tier, top-to-bottom lines from each file. Skip blank lines and lines starting with `#`. Map each line to an operation (`set`, `append`, `remove`, `delete`).

For each row, form one part:

```text
{tier}{digest_pair}{file}{digest_pair}{class}{digest_pair}{op}{digest_pair}{body}
```

Sort all parts lexicographically ascending, join with `digest_joiner`, UTF-8 encode, and take SHA-256 hex lowercase.

## Local readiness surface

A short local readiness probe may report convergence when the input-tree digest matches the last stored digest. That probe does not replace inspect: graded results always come from the regenerated `/app/output/rule_lineage.json` artifact.
