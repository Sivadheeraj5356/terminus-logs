# Relocation report layout

Write exactly one file: `/app/artifacts/relocation_consistency_report.json`.
UTF-8 JSON with a trailing newline. Repeated runs on the same inputs must be
byte identical.

## Top level

Keys are exactly `summary` then `batches`. No other top level keys.

### JSON key order (normative)

Top level: `summary`, `batches`.

`summary`: `batches_analyzed`, `failed_batches`, `clean_batches`,
`total_findings`, `replay_runs`, `replay_passed`.

Each `batches[]` element: `batch_id`, `relocation_ok`, `findings`,
`mapping_ok`, `rewrite_ok`, `isolation_ok`, `identity_ok`, `rollback_ok`,
`replay`.

`replay`: `schedules_run`, `schedules_passed`, `stable`.

Each `findings[]` element: `kind`, `subject`, `expected`, `observed`,
`rule_id`.

Within each batch row, `findings` MUST be globally sorted lexicographically by
`(kind, subject, expected, observed)` after deduplication. Do not leave
findings in check-group insertion order. `rule_id` is not a sort key.

## summary

`clean_batches` counts rows with `relocation_ok` true.
`failed_batches` counts rows with `relocation_ok` false.
`batches_analyzed` must equal the number of `batch_NN.json` files under the
batch directory (twenty for bundled `/app/reloc-batches`).
`total_findings` sums finding list lengths.
`replay_runs` sums `replay.schedules_run`.
`replay_passed` sums `replay.schedules_passed`.

## batches

One object per file `batch_01.json` through `batch_20.json`, sorted by
`batch_id` ascending. Ignore other `*.json` files in that directory.
For `/app/reloc-batches/`, `batch_id` must match the basename without
extension.

When findings are empty, emit `[]` never `null`.

When a batch has no `replay.schedules` (missing or empty), emit
`schedules_run` 0, `schedules_passed` 0, and `stable` true. Otherwise compute
replay fields from RELOCATION_SPEC (including `stable` precedence under
`prefix_stable_on_findings` / `full_unstable_on_findings`).

Orphan findings use `observed` equal to the literal string `present` (see
RELOCATION_SPEC).

## Integrity

Do not edit bundled batches or specification documents. The verifier
recomputes each file SHA256 against its checksum manifest.

Honor `RELOC_BATCH_DIR` when set for alternate fixture directories used by the
verifier probes.
