# Report schema

Write `/app/output/report.json` (path from `--output`) with two-space indentation
and exactly one trailing newline. Top-level keys in this exact order:

1. `request_rows`
2. `quote_rows`
3. `event_rows`
4. `pcr_rows`
5. `reference_match_rows`
6. `counter_rows`
7. `nonce_rows`
8. `conflict_rows`
9. `summary`

Processing order (`received_at`, `request_id`) is distinct from report sort order.

## `request_rows`

One row per structurally valid request. Sort by `request_id`.

| Field | Type | Notes |
|---|---|---|
| request_id | string | |
| received_at | number | |
| device_id | string | |
| status | string | `accepted` or `rejected` |
| reason_or_null | string or null | null when accepted; else exact reason token |
| nonce_consumed_by_this_request | boolean | |
| selected_pcr_count | number | `0` if rejected before quote replay |
| replayed_event_count | number | `0` if rejected before replay |
| matched_rule_count | number | `0` before appraisal |
| failed_rule_count | number | `0` before appraisal |
| counter_committed | boolean | |

## `quote_rows`

Emit only when the quote parsed successfully. Sort by `request_id`.

| Field | Type | Notes |
|---|---|---|
| request_id | string | |
| attestation_key_id | string | |
| attestation_key_fingerprint | string | 64-char lowercase hex |
| magic_hex | string | 8-char lowercase hex of magic u32 |
| attestation_type | string | always `quote` |
| qualified_signer_hex | string | 68-char lowercase |
| extra_data_hex | string | 64-char lowercase |
| clock | number | |
| reset_count | number | |
| restart_count | number | |
| safe | number | 0 or 1 |
| firmware_version | number | |
| selected_pcrs | array[number] | sorted unique |
| quoted_pcr_digest | string | 64-char lowercase |
| computed_pcr_digest_or_null | string or null | set when replay completed |
| signature_status | string | `valid`, `invalid`, or `not_checked` |
| pcr_digest_status | string | `matched`, `mismatched`, or `not_checked` |

## `event_rows`

Emit only for requests that reach event-log replay. Sort by
`(request_id, event_seq)`.

| Field | Type | Notes |
|---|---|---|
| request_id | string | |
| event_log_id | string | |
| event_seq | number | |
| pcr_index | number | |
| event_type | string | |
| component | string | |
| version | string | |
| measurement_digest | string | |
| policy_status | string | `matched`, `allowed_unknown`, `rejected`, `not_evaluated` |
| matched_rule_id_or_null | string or null | at most one |

## `pcr_rows`

For every request that completes PCR replay, emit exactly four rows for PCR
indexes `0`, `2`, `4`, `7`. Sort by `(request_id, pcr_index)`.

| Field | Type |
|---|---|
| request_id | string |
| pcr_index | number |
| selected | boolean |
| policy_required | boolean |
| replayed_value | string (64-char lowercase hex) |

## `reference_match_rows`

One row per policy measurement rule for requests that reach reference appraisal.
Sort by `(request_id, rule_id)`.

| Field | Type | Notes |
|---|---|---|
| request_id | string | |
| policy_id | string | |
| rule_id | string | |
| rule_kind | string | `required`, `optional`, `forbidden` |
| matched_event_sequences | array[number] | sorted unique |
| status | string | `matched`, `absent_allowed`, `missing`, `duplicate`, `version_mismatch`, `digest_mismatch`, `forbidden_present` |
| reason_or_null | string or null | null or one of: `required_event_missing`, `multiple_matching_events`, `event_version_not_allowed`, `event_digest_not_allowed`, `forbidden_event_present` |

Do not emit unspecified prose.

## `counter_rows`

One row per request whose quote parsed successfully. Sort by `request_id`.

| Field | Type | Notes |
|---|---|---|
| request_id | string | |
| device_id | string | |
| prior_reset_count | number | |
| prior_restart_count | number | |
| prior_clock | number | |
| quoted_reset_count | number | |
| quoted_restart_count | number | |
| quoted_clock | number | |
| safe | number | |
| status | string | `accepted`, `unsafe`, `rollback`, `not_checked` |
| committed | boolean | |

If rejected before the counter stage: `status=not_checked`, `committed=false`.

## `nonce_rows`

One row per nonce challenge. Sort by `nonce_id`.

| Field | Type | Notes |
|---|---|---|
| nonce_id | string | |
| device_id | string | |
| issued_at | number | |
| expires_at | number | |
| initial_status | string | `available` or `consumed` from `initially_consumed_by_request_id_or_null` |
| final_status | string | `available` or `consumed` after replay |
| consumed_by_request_id_or_null | string or null | final consumer if consumed |

## `conflict_rows`

Emit for request-level security/policy conflicts that have a concrete subject.
Do **not** emit for `quote_malformed` or `signature_malformed`.

| Field | Type | Notes |
|---|---|---|
| request_id | string | |
| conflict_type | string | closed vocabulary below |
| subject | string | exact reason-specific subject from the mapping |
| reason_code | string | exact request reason token |
| related_values | array[string] | constructed then deduplicated then sorted |

Sort by `(request_id, conflict_type, subject, reason_code)`.

`related_values` sorting is internal to each row. Conflict-row array sorting is
a separate operation and must not sort by `rule_id`, `event_seq`, physical input
order, or `related_values`.

### Closed conflict_type vocabulary

Exactly these values are valid:

```text
identity
nonce
pcr
counter
firmware
measurement
event_order
```

No other conflict type is valid.

### Normative exhaustive conflict-row mapping

Every row must use the exact `conflict_type`, `subject`, `reason_code`, and
`related_values` rule below.

A semantically plausible alternative is invalid.

Field-path notation such as `request.device_id`, `nonce.nonce_id`, or
`quote.safe` means substitute the actual runtime string value of that field
(for example `"dev-edge"`). Never emit the path text itself as the subject or
as a related value.

`related_values` is constructed from the listed source values, converted to
strings exactly as stated, deduplicated, then sorted lexicographically in
ascending order.

All current values are ASCII; use ordinary ascending string order.

#### Identity conflicts

**`device_unknown`**

- conflict_type: `identity`
- subject: `request.device_id`
- related_values: `[request.device_id]`

**`attestation_key_unknown`**

- conflict_type: `identity`
- subject: `request.attestation_key_id`
- related_values: `[request.attestation_key_id]`

**`reference_policy_unknown`**

- conflict_type: `identity`
- subject: `request.policy_id`
- related_values: `[request.policy_id]`

**`event_log_unknown`**

- conflict_type: `identity`
- subject: `request.event_log_id`
- related_values: `[request.event_log_id]`

**`attestation_key_device_mismatch`**

- conflict_type: `identity`
- subject: `request.attestation_key_id`
- related_values: `[attestation_key.device_id, request.device_id]`

**`device_class_not_allowed`**

- conflict_type: `identity`
- subject: `device.device_class`
- related_values: `[device.device_class, request.policy_id]`

**`quote_magic_invalid`**

- conflict_type: `identity`
- subject: quote magic as exactly eight lowercase hexadecimal characters without `0x`
- related_values: `[subject]`

**`quote_type_invalid`**

- conflict_type: `identity`
- subject: `"0x"` followed by exactly four lowercase hexadecimal digits
- related_values: `[subject]`

**`qualified_signer_mismatch`**

- conflict_type: `identity`
- subject: `request.attestation_key_id`
- related_values: `[quote qualified_signer as lowercase hexadecimal, attestation_key.qualified_name_hex]`

**`attestation_key_not_valid`**

- conflict_type: `identity`
- subject: `request.attestation_key_id`
- related_values: `[request.received_at, attestation_key.valid_from, attestation_key.valid_until]` as unsigned decimal strings

**`quote_signature_invalid`**

- conflict_type: `identity`
- subject: `request.attestation_key_id`
- related_values: `[request.attestation_key_id]`

#### Nonce conflicts

**`nonce_unknown`**

- conflict_type: `nonce`
- subject: `request.nonce_id`
- related_values: `[request.nonce_id]`

**`nonce_device_mismatch`**

- conflict_type: `nonce`
- subject: `request.nonce_id`
- related_values: `[nonce.device_id, request.device_id]`

**`nonce_not_yet_valid`**

- conflict_type: `nonce`
- subject: `request.nonce_id`
- related_values: `[request.received_at, nonce.issued_at]` as unsigned decimal strings

**`nonce_expired`**

- conflict_type: `nonce`
- subject: `request.nonce_id`
- related_values: `[request.received_at, nonce.expires_at]` as unsigned decimal strings

**`nonce_consumed`**

- conflict_type: `nonce`
- subject: `request.nonce_id`
- related_values: `[the request_id that previously consumed the nonce]`

**`nonce_mismatch`**

- conflict_type: `nonce`
- subject: `request.nonce_id`
- related_values: `[quote.extra_data as lowercase hexadecimal, nonce.nonce_hex]`

#### PCR conflicts

**`quote_pcr_selection_invalid`**

- conflict_type: `pcr`
- subject: `request.policy_id`
- Construct `selected_set` = quote selected PCR indexes sorted ascending, joined by `","` with no spaces.
- Construct `required_set` = policy required PCR indexes sorted ascending, joined by `","` with no spaces.
- related_values: `[selected_set, required_set]` then deduplicate and lexical-sort.

**`event_log_device_mismatch`**

- conflict_type: `pcr`
- subject: `request.event_log_id`
- related_values: `[event_log.device_id, request.device_id]`

**`pcr_digest_mismatch`**

- conflict_type: `pcr`
- subject: `request.event_log_id`
- related_values: `[quote quoted-PCR digest as lowercase hexadecimal, computed selected-PCR digest as lowercase hexadecimal]`

#### Counter and firmware conflicts

**`clock_unsafe`**

- conflict_type: `counter`
- subject: `request.device_id`
- related_values: `[quote.safe as an unsigned decimal string]`

**`counter_rollback`**

- conflict_type: `counter`
- subject: `request.device_id`
- related_values source values (as unsigned decimal strings): prior reset_count, prior restart_count, prior clock, quoted reset_count, quoted restart_count, quoted clock.
- Then deduplicate and sort lexicographically.
- Do not preserve semantic numeric ordering after converting to strings.
- Do not preserve prior-versus-quoted grouping in the final array.

**`firmware_not_allowed`**

- conflict_type: `firmware`
- subject: `quote.firmware_version` as an unsigned decimal string
- related_values: `[subject]`

#### Measurement and event-order conflicts

**`reference_measurement_mismatch`**

For every reference-measurement rejection, including required rule missing,
multiple matching events, version not allowed, measurement digest not allowed,
forbidden event present, and unknown event rejected, use exactly:

- conflict_type: `measurement`
- subject: `request.policy_id`
- reason_code: `reference_measurement_mismatch`
- related_values: `[request.policy_id]`

Do not use the failed `rule_id` as `conflict_rows.subject`.

Do not place failed rule IDs, event IDs, event sequences, components, versions,
or digests in this conflict row.

Rule-level evidence belongs in `reference_match_rows` and `event_rows`.

The conflict row intentionally projects the policy-level decision.

This rule is the same regardless of which measurement rule failed first.

**`event_order_violation`**

Let `before = failing order constraint before_rule_id` and
`after = failing order constraint after_rule_id`.

- conflict_type: `event_order`
- subject: `before + "->" + after`
- reason_code: `event_order_violation`
- related_values: `[before, after]` then deduplicate and sort lexicographically.

The arrow contains no surrounding whitespace.

Do not use: `policy_id`, one endpoint alone, event sequence values,
`"before:after"`, or `"before -> after"`.

### Conflict omission rules

Do not emit a conflict row for:

- `quote_malformed`
- `signature_malformed`

Every other request rejection in the published first-failure precedence list
emits exactly one conflict row according to the exhaustive table.

Accepted requests emit no conflict row.

Do not add conflicts for inner reference-rule reasons such as
`required_event_missing`, `multiple_matching_events`,
`event_version_not_allowed`, `event_digest_not_allowed`, or
`forbidden_event_present`. Those tokens belong to
`reference_match_rows.reason_or_null`. The request-level conflict remains
`reference_measurement_mismatch`.

## `summary`

Derive exclusively from emitted rows (do not maintain independent counters):

| Field | Derivation |
|---|---|
| request_count | len(request_rows) |
| accepted_request_count | status==accepted |
| rejected_request_count | status==rejected |
| quote_row_count | len(quote_rows) |
| event_row_count | len(event_rows) |
| pcr_row_count | len(pcr_rows) |
| reference_match_row_count | len(reference_match_rows) |
| matched_rule_count | sum of request_rows.matched_rule_count |
| failed_rule_count | sum of request_rows.failed_rule_count |
| initially_consumed_nonce_count | nonce_rows with initial_status==consumed |
| finally_consumed_nonce_count | nonce_rows with final_status==consumed |
| counter_commit_count | counter_rows with committed==true |
| conflict_count | len(conflict_rows) |
