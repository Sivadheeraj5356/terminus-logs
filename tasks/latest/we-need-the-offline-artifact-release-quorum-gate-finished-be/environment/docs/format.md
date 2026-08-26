# release audit report

Output path: `/app/output/release_audit.json`

Top-level fields:

- `bundle_id` — copied from the input bundle
- `eval_profile` — always `artifact-quorum-v1`
- `results` — sorted by `query_id` ascending before write
- `stats` — counters for the run
- `state_digest` — lowercase hex per `/app/docs/digest_contract.md`

Each `results` row:

| field | type | meaning |
|-------|------|---------|
| `query_id` | string | from the query |
| `decision` | string | `allow` or `deny` |
| `reason` | string | see reason codes |
| `quorum_weight` | int | sum of custodian weights whose signatures verified; 0 when none verified |
| `signatures_verified` | int | count of signatures that passed Ed25519 verification |
| `unique_custodians` | int | count of distinct `custodian_id` values present in the query signature list |

`stats` object:

| field | type |
|-------|------|
| `queries_total` | int |
| `allowed` | int |
| `denied` | int |
| `signature_failures` | int |
| `quorum_failures` | int |
| `revoked_hits` | int |

Reason codes (exact strings):

- `quorum_ok` — allow only
- `scope_malformed` — `scope` is not exactly three non-empty segments separated by `|`
- `epoch_future` — `release_epoch` exceeds `eval_at + max_future_skew_sec` from runtime policy
- `epoch_stale` — `eval_at - release_epoch` exceeds `max_release_age_sec` (strictly greater than the limit)
- `duplicate_custodian` — the same `custodian_id` appears more than once in the signature list
- `unknown_custodian` — signature references an id absent from bundle `custodians`
- `revoked_custodian` — signature references an id listed in `revoked_custodians`
- `signature_invalid` — Ed25519 verification failed for a listed signature
- `insufficient_quorum` — verified weight sum is below `min_weight`

Evaluation order for a query (stop at first failure):

1. Scope format
2. Release epoch window (`epoch_future`, then `epoch_stale`) using `max_future_skew_sec = 300` and `max_release_age_sec = 86400`
3. Signature list scan in array order (`duplicate_custodian`, `unknown_custodian`, `revoked_custodian`, `signature_invalid`)
4. Weight sum versus `min_weight` (`insufficient_quorum` or `quorum_ok`)

`signature_failures` increments when the terminal reason is `signature_invalid`. `quorum_failures` increments for `insufficient_quorum`. `revoked_hits` increments for `revoked_custodian`.

Bundle JSON layout:

- `bundle_id`, `custodians` map (`custodian_id` → `{ "public_key_hex": "<64 lowercase hex>", "weight": <positive int> }`)
- `revoked_custodians` string array
- `queries` array of `{ query_id, eval_at, artifact_sha256_hex, scope, release_epoch, min_weight, signatures }`

Each signature entry: `{ "custodian_id": "...", "signature_hex": "<128 lowercase hex>" }`.
