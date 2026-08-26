# Input schema

All candidate-visible inputs live under the directory passed as `--data-dir`.
Unknown top-level fields on any JSON object are **fatal**. Required fields must
be present with the documented JSON types. Identifiers are nonempty strings;
loaders must strip surrounding whitespace and reject empty results. Persist the
stripped form.

Hex strings must be lowercase, even length, valid hexadecimal, and exactly the
documented character length. Reject `0x` prefixes, uppercase, whitespace, and
odd lengths.

## `devices.json`

Top-level: array. Each record:

| Field | Type | Rules |
|---|---|---|
| device_id | string | nonempty normalized; globally unique |
| device_class | string | nonempty normalized |
| last_reset_count | number | u32 |
| last_restart_count | number | u32 |
| last_clock | number | u64 |

## `attestation_keys.json`

Top-level: array. Each record:

| Field | Type | Rules |
|---|---|---|
| attestation_key_id | string | nonempty normalized; globally unique |
| device_id | string | must reference a registered device |
| qualified_name_hex | string | exactly 68 lowercase hex chars (34 bytes) |
| public_key_sec1_hex | string | exactly 130 lowercase hex chars; 65-byte SEC1 `0x04\|\|X\|\|Y` on P-256 |
| valid_from | number | u64 Unix seconds |
| valid_until | number | u64; require `valid_from <= valid_until` |

## `reference_policies.json`

Top-level: array. Each policy:

| Field | Type | Rules |
|---|---|---|
| policy_id | string | nonempty normalized; globally unique |
| allowed_device_classes | array[string] | nonempty normalized identifiers; unique |
| required_pcrs | array[number] | subset of `{0,2,4,7}`; unique; nonempty; store sorted |
| allowed_firmware_versions | array[number] | u64 values; unique |
| require_safe | boolean | |
| unknown_event_mode | string | `allow` or `reject` |
| measurement_rules | array | see below |
| order_constraints | array | see below |

### Measurement rule

| Field | Type | Rules |
|---|---|---|
| rule_id | string | nonempty; unique within policy |
| kind | string | `required`, `optional`, or `forbidden` |
| pcr_index | number | `0`, `2`, `4`, or `7` |
| event_type | string | nonempty normalized |
| component | string | nonempty normalized |
| allowed_versions | array[string] | sorted unique nonempty strings |
| allowed_digests | array[string] | sorted unique 64-char lowercase SHA-256 hex |

For `required`/`optional`: both allow-lists nonempty. For `forbidden`: both
arrays empty. Selector `(pcr_index, event_type, component)` unique within policy.

### Order constraint

| Field | Type | Rules |
|---|---|---|
| before_rule_id | string | must exist in same policy |
| after_rule_id | string | must exist; not equal to before |

Reject duplicate constraints, cycles in the constraint graph, and constraints
involving forbidden rules.

## `event_logs.json`

Top-level: array. Each snapshot:

| Field | Type | Rules |
|---|---|---|
| event_log_id | string | nonempty normalized; globally unique |
| device_id | string | must reference a registered device |
| events | array | |

### Event

| Field | Type | Rules |
|---|---|---|
| event_seq | number | u32; unique within the log |
| pcr_index | number | `0`, `2`, `4`, or `7` |
| event_type | string | nonempty normalized |
| component | string | nonempty normalized |
| version | string | nonempty |
| measurement_digest | string | 64 lowercase hex chars |

Gaps in `event_seq` are allowed. Physical array order is irrelevant; semantic
order is ascending numeric `event_seq`.

## `nonce_challenges.json`

Top-level: array. Each record:

| Field | Type | Rules |
|---|---|---|
| nonce_id | string | nonempty normalized; globally unique |
| device_id | string | must reference a registered device |
| nonce_hex | string | exactly 64 lowercase hex chars |
| issued_at | number | u64 |
| expires_at | number | u64; require `issued_at <= expires_at` |
| initially_consumed_by_request_id_or_null | string or null | if string, nonempty; need not reference a current request |

## `quote_requests.ndjson`

One JSON object per nonempty line. Physical order irrelevant.

| Field | Type | Rules |
|---|---|---|
| request_id | string | nonempty normalized; globally unique across requests |
| received_at | number | u64 Unix seconds |
| device_id | string | |
| attestation_key_id | string | |
| nonce_id | string | |
| policy_id | string | |
| event_log_id | string | |
| quote_hex | string | lowercase hex; length ≤ `maximum_quote_bytes` * 2 |
| signature_hex | string | lowercase hex; length ≤ `maximum_signature_bytes` * 2 |

Unknown device/key/nonce/policy/event-log IDs on a request are **request-level**
rejections, not fatal, when the dataset itself is structurally valid.

## `policy.json`

Object with exactly these fields (unknown fields fatal):

| Field | Type |
|---|---|
| maximum_devices | number (u32) |
| maximum_attestation_keys | number |
| maximum_reference_policies | number |
| maximum_event_logs | number |
| maximum_events_per_log | number |
| maximum_total_events | number |
| maximum_nonce_challenges | number |
| maximum_requests | number |
| maximum_quote_bytes | number |
| maximum_signature_bytes | number |

Exceeding a limit is fatal. Do not place hidden semantic policy here.

## Fatal structural conditions

Missing required file; unreadable JSON/NDJSON; wrong top-level type; unknown
fields; missing/wrong-typed fields; duplicate identity records (see table
below); malformed global hex; invalid P-256 public point; invalid timestamp
ranges; unknown structural cross-file identity in global records; unsupported
PCR in global event data; duplicate measurement-rule selectors;
unknown/cyclic/forbidden order constraints; invalid forbidden-rule arrays;
policy limit exceeded.

### Whole-run fatal duplicate identity conditions

| File or scope | Identity field | Required uniqueness |
|---|---|---|
| `devices.json` | `device_id` | unique among device records |
| `attestation_keys.json` | `attestation_key_id` | unique among attestation-key records |
| `reference_policies.json` | `policy_id` | unique among policy records |
| each policy | `rule_id` | unique within that policy |
| `event_logs.json` | `event_log_id` | unique among event-log records |
| each event log | `event_seq` | unique within that event log |
| `nonce_challenges.json` | `nonce_id` | unique among nonce records |
| `quote_requests.ndjson` | `request_id` | unique among requests |

A duplicate in any listed identity namespace is fatal before chronological
request processing.

Do not:

- keep the first record;
- keep the last record;
- merge records;
- emit one request-level rejection;
- emit a partial report.

The same text value may appear in different identity namespaces unless another
published cross-file rule forbids it. For example, uniqueness of `device_id`
does not imply that no `policy_id` may use the same string.

On fatal failure: remove stale requested output before processing; exit nonzero;
write nonempty stderr; leave no temporary output sibling; emit no partial report.
