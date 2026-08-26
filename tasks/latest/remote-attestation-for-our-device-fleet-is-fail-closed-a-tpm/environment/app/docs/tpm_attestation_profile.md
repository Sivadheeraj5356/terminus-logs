# Bounded TPM 2.0-inspired offline attestation profile

This document is normative for the candidate attestor.

## Scope

Supported: one SHA-256 PCR bank; PCR indexes `{0,2,4,7}`; one quote hash algorithm
(`TPM_ALG_SHA256`); one signature algorithm (`TPM_ALG_ECDSA` over P-256); bounded
`TPMS_ATTEST` quote body; bounded `TPMT_SIGNATURE`; JSON event-log snapshots;
reference-measurement policies with required/optional/forbidden rules and order
constraints.

Not in scope: full TPM 2.0 structures, unrestricted EFI/TCG binary event logs,
multiple PCR banks, RSA, certificate chains, TPM hardware/simulators.

## Request processing order

Process requests sorted by `(received_at, request_id)` ascending. Physical NDJSON
order is irrelevant. Evaluate each device independently.

## Quote wire encoding (`quote_hex`)

`quote_hex` is the exact signed `TPMS_ATTEST` body (no outer `TPM2B_ATTEST.size`).
All integers are unsigned big-endian. Reject truncated fields, oversized
length-prefixed values, unsupported constants, and trailing bytes.

Field order:

| Field | Encoding | Requirement |
|---|---|---|
| magic | u32 | `0xff544347` (`TPM_GENERATED_VALUE`) |
| type | u16 | `0x8018` (`TPM_ST_ATTEST_QUOTE`) |
| qualified_signer_length | u16 | `34` |
| qualified_signer | 34 bytes | exact match to key `qualified_name_hex` |
| extra_data_length | u16 | `32` |
| extra_data | 32 bytes | exact verifier nonce bytes |
| clock | u64 | |
| reset_count | u32 | |
| restart_count | u32 | |
| safe | u8 | `0` or `1` |
| firmware_version | u64 | |
| pcr_selection_count | u32 | `1` |
| hash_algorithm | u16 | `0x000b` (`TPM_ALG_SHA256`) |
| sizeof_select | u8 | `3` |
| pcr_select | 3 bytes | see bitset |
| pcr_digest_length | u16 | `32` |
| pcr_digest | 32 bytes | |

### PCR selection bitset

Physical bit numbering (do not infer alternatives):

- byte 0 bit 0 → PCR 0
- byte 0 bit 2 → PCR 2
- byte 0 bit 4 → PCR 4
- byte 0 bit 7 → PCR 7

Every other bit must be zero. At least one supported PCR must be selected.

## Signature wire encoding (`signature_hex`)

| Field | Encoding | Requirement |
|---|---|---|
| signature_algorithm | u16 | `0x0018` (`TPM_ALG_ECDSA`) |
| hash_algorithm | u16 | `0x000b` |
| r_length | u16 | `32` |
| r | 32 bytes | |
| s_length | u16 | `32` |
| s | 32 bytes | |

Verify ECDSA P-256 with SHA-256 over the **exact decoded `quote_hex` bytes**.
Do not reserialize. Public key is a 65-byte uncompressed SEC1 point
`0x04 || X || Y`. Reject invalid points, points not on P-256, zero `r`/`s`,
scalars outside the P-256 range, and invalid signatures. High-S signatures that
are mathematically valid are accepted (no low-S requirement).

## Digests

All public hex strings: lowercase, even length, valid hex, exact documented byte
length. No `0x` prefix, uppercase, or whitespace.

- Event measurement: decode `measurement_digest` to 32 bytes (do not hash hex text).
- PCR extend: `SHA-256(old_pcr_bytes || measurement_digest_bytes)`.
- Selected PCR digest: sort selected indexes ascending; concatenate final 32-byte
  PCR values; `SHA-256` of concatenation.
- Signature message digest: `SHA-256(exact quote bytes)`.
- Attestation key fingerprint (reporting only):
  `SHA-256(decoded public_key_sec1_hex)` as lowercase hex.

Initial PCR value for every supported index: 32 zero bytes.

## First-failure precedence

For each request, stop at the first applicable reason:

1. `device_unknown`
2. `attestation_key_unknown`
3. `nonce_unknown`
4. `reference_policy_unknown`
5. `event_log_unknown`
6. `attestation_key_device_mismatch`
7. `device_class_not_allowed`
8. `quote_malformed`
9. `signature_malformed`
10. `quote_magic_invalid`
11. `quote_type_invalid`
12. `qualified_signer_mismatch`
13. `attestation_key_not_valid`
14. `quote_signature_invalid`
15. `nonce_device_mismatch`
16. `nonce_not_yet_valid`
17. `nonce_expired`
18. `nonce_consumed`
19. `nonce_mismatch`
20. `quote_pcr_selection_invalid`
21. `event_log_device_mismatch`
22. `pcr_digest_mismatch`
23. `clock_unsafe`
24. `counter_rollback`
25. `firmware_not_allowed`
26. `reference_measurement_mismatch`
27. `event_order_violation`

Inside reference appraisal: evaluate measurement rules in lexicographic `rule_id`
order (first failing rule wins). Evaluate order constraints only after all
measurement rules pass, ordered by `(before_rule_id, after_rule_id)`.

## Nonce usability

A nonce is usable only when `nonce.device_id == request.device_id`,
`issued_at <= received_at <= expires_at`, the nonce is not already consumed, and
`quote.extra_data` equals the nonce bytes.

### Nonce consumption gate

Consume the nonce immediately after all of the following succeed: request
references resolve; quote and signature parse; magic/type/signer valid; key valid
for `received_at`; signature valid; nonce device/window/unused; extra_data matches.

The nonce remains consumed even if the request later rejects for PCR selection,
event-log device mismatch, PCR digest mismatch, unsafe clock, counter rollback,
firmware rejection, reference mismatch, or event-order violation.

Failures before this gate must not consume the nonce.

## Counter monotonicity

Compare quote counters with the device’s last committed state:

| Condition | Result |
|---|---|
| `quoted.reset < prior.reset` | `counter_rollback` |
| same reset and `quoted.restart < prior.restart` | `counter_rollback` |
| same reset+restart and `quoted.clock < prior.clock` | `counter_rollback` |
| `quoted.reset > prior.reset` | allow any restart/clock (new reset epoch) |
| same reset and `quoted.restart > prior.restart` | allow any clock (new restart epoch) |
| same reset+restart | require `quoted.clock >= prior.clock` |

### Counter commit gate

Commit `reset_count`, `restart_count`, and `clock` only after: nonce-consumption
gate succeeded; PCR selection supported and equals policy `required_pcrs`; event
log belongs to the device; PCR replay completed; computed digest matches quoted
digest; safe-clock policy passed; counter monotonicity passed.

Committed counters remain even if the request later rejects for
`firmware_not_allowed`, `reference_measurement_mismatch`, or
`event_order_violation`.

## State mutation survival table

| Failure class | Nonce | Counters |
|---|---|---|
| Pre-auth failures through `nonce_mismatch` (see list below) | unchanged | unchanged |
| `quote_pcr_selection_invalid`, `event_log_device_mismatch`, `pcr_digest_mismatch`, `clock_unsafe`, `counter_rollback` | consumed | prior value |
| `firmware_not_allowed`, `reference_measurement_mismatch`, `event_order_violation` | consumed | quoted values committed |
| accepted | consumed | quoted values committed |

No mutation (nonce or counters): `device_unknown`, `attestation_key_unknown`,
`nonce_unknown`, `reference_policy_unknown`, `event_log_unknown`,
`attestation_key_device_mismatch`, `device_class_not_allowed`, `quote_malformed`,
`signature_malformed`, `quote_magic_invalid`, `quote_type_invalid`,
`qualified_signer_mismatch`, `attestation_key_not_valid`,
`quote_signature_invalid`, `nonce_device_mismatch`, `nonce_not_yet_valid`,
`nonce_expired`, `nonce_consumed`, `nonce_mismatch`.

## Attestation-key validity

Inclusive: `valid_from <= received_at <= valid_until`. Key must belong to the
request device.

## PCR selection vs policy

Selected PCR index set must equal policy `required_pcrs` exactly. Otherwise
`quote_pcr_selection_invalid` (also for unsupported bits, empty selection,
wrong bank/hash constants already rejected at parse where applicable).

## Safe-clock and firmware

If `require_safe` is true, quote `safe` must be `1` else `clock_unsafe`.
`firmware_version` must appear in `allowed_firmware_versions` else
`firmware_not_allowed`.

## Reference-measurement appraisal

An event matches a rule when `(pcr_index, event_type, component)` equal.
Duplicate selectors within a policy are structurally forbidden.

- **required**: exactly one matching event; version in `allowed_versions`; digest
  in `allowed_digests`.
- **optional**: zero or one match; absent → `absent_allowed`; present → same
  version/digest checks.
- **forbidden**: no matching event may exist.
- **unknown event**: matches no rule; `unknown_event_mode=allow` →
  `allowed_unknown`; `reject` → `reference_measurement_mismatch`.
- **order constraint**: when both endpoints have exactly one selected matching
  event, require `before.event_seq < after.event_seq` else `event_order_violation`.

Reference appraisal has two reporting levels.

`reference_match_rows` reports rule-level outcomes and may name the failed
`rule_id`.

`request_rows` and `conflict_rows` report the policy-level first-failure decision.

For `reference_measurement_mismatch`, `conflict_rows` therefore uses `policy_id`
as both subject and the sole related value.

`event_order_violation` is the exception because the failed order edge itself
is the conflict subject.

## Hexadecimal and fatal/request-level behavior

See `input_schema.md` and `report_schema.md` for field-level rules, fatal
structural errors, and report projection rules.
