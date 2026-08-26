# Feasibility certificate layout

Target path: `/app/output/feasibility_certificate.json`

Top-level fields:

- `violations` (integer): counts dimensional mismatches; graded runs must report zero.
- `rows` (array): one object per matrix emission in set/item/band walk order (a manifest may appear more than once when rematerialized under a later set stem).

Each row object:

| field | type | meaning |
|-------|------|---------|
| manifest_id | string | fixture identifier |
| unit_tag | string | comma-joined ordered slot tokens including trailing `rev=` |
| scope_band | string | `p7` or `p8` |
| canonical_byte_digest | string | 16 lowercase hex chars |
| cache_epoch | integer | durable epoch for this manifest (≥1) |
| journal_tip_hex | string | 8 lowercase hex chars |
| seal_window | integer | seal table index used for this row (≥0) |

## Reduction authority

Row fields must agree with the closed reduction implied by:

1. Profile TOML under `/app/environment/profiles/` (`band`, `annex_keys`, `scope_letter`).
2. KEY=VALUE lines in `/app/environment/fixtures/slices/q46.txt`.
3. Journal, parent-tip salt, and tip rules in `docs/stage_rules.md` and `docs/tip_chain.md`.
4. Seal window selection in `docs/seal_windows.md`.
5. Crash truncation and surviving-line lineage in `docs/recovery.md`.
6. Field notes in `docs/w8/overview.md` and annex notes in `docs/w9/q46.md`.

When prose and the slice disagree, the slice wins for annex prefix, order, seal table, window modulus, and stage root. Profile TOML wins for per-band `scope_letter` and `annex_keys`.

The single-token `SEAL=` line in the slice is retained for legacy probes only. Graded digests select from `SEAL_TABLE` via the seal-window rule mixed with GEN. Graded digests also mix the fixture `namespace` and the pre-append journal tip (`parent_tip`); omitting either salt fails closed reduction even when wire, seal window id, and epoch look locally correct.

## JSON boundary

Matrix files are standard JSON arrays of objects, not delimiter-separated text.
Object braces and quotes inside JSON strings are data, JSON escapes are decoded
before label and annotation tokens are formed, and the emitted certificate must
remain valid JSON for those decoded values. In particular, a `}` inside a label
value does not end an input object, and quotes or backslashes in a token must be
escaped when that token is serialized in the certificate. Digests and journal
frames use the decoded token bytes, not the source escape spelling.

## Recovery before matrix entry

Run `/app/environment/migrations/wipe7.sh` once before certification when stale stage artifacts exist. The matrix driver also invokes stage mending at the start of each emit; incomplete journal tails must not survive into tips.

## Graded artifact

Terminal `feasibility_certificate.json` from the full matrix command is graded. Interim counts under `fixtures/q_counts/q3.json` are diagnostic only. Stage smoke files under `/app/output/stage` may look ready while the certificate is wrong.
