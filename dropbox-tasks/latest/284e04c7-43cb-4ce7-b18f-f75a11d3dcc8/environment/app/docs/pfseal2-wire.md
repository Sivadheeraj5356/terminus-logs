# PFSEAL2 label format

Prefect image builders use exactly one of two transports. The direct transport places one standard, padded RFC 4648 base64 string in `io.prefect.pfseal`. The chunked transport omits that label and places a canonical JSON manifest in `io.prefect.pfseal.manifest`, plus numbered labels `io.prefect.pfseal.part.000` onward. Having both transports is invalid.

The chunk manifest has exactly `count` and `sha256`, encoded as minified key-sorted JSON. `count` is an integer from 2 through 32 and `sha256` is lowercase SHA-256 hex over the UTF-8 bytes of the concatenated chunks. Every index from zero through `count-1` must occur once using three decimal digits; each value is an ASCII string of 1 through 1024 characters. Any `io.prefect.pfseal.part.` label outside that exact index set is invalid. Concatenate chunks in numeric order before base64 validation.

The resulting string uses canonical padded RFC 4648 base64. Whitespace, missing padding, URL-safe alphabet characters, and encodings that do not round-trip byte-for-byte through standard base64 are invalid. The decoded label has this exact layout; multi-byte integers are unsigned big-endian.

| Offset | Size | Field |
| --- | ---: | --- |
| 0 | 7 | ASCII `PFSEAL2` |
| 7 | 1 | flags; currently `0x00` only |
| 8 | 2 | key version, 1 through 65535 |
| 10 | 12 | AES-GCM nonce |
| 22 | 4 | ciphertext byte count `N` |
| 26 | 32 | header HMAC |
| 58 | `N` | ciphertext |
| `58+N` | 16 | AES-GCM tag |

`N` may be 1 through 1,048,576. The decoded length must be exactly `74+N`; trailing bytes are not extensions. `headerCore` means bytes 0 through 25. The 32-byte header field is `HMAC-SHA256(macKey, headerCore)`. Compare it in constant time before attempting GCM authentication. AES-256-GCM uses `encKey`, the 12-byte nonce, a 16-byte tag, and `headerCore || headerHmac` as additional authenticated data.

## Deployment key schedule

Resolve metadata independently for each job at its `metadata_revision`. For every metadata key, its effective value and effective revision come from the row with the greatest `revision` not exceeding that job revision. The required keys are `prefect.workspace-id`, `prefect.work-pool`, the three keys `pfseal.key.v{V}.share0`, `share1`, and `share2`, and `pfseal.key.v{V}.attestation`, where `{V}` is the envelope version. A missing key, malformed value, duplicate row at the effective revision, or incorrect decoded share length is a key-metadata failure.

Share 0 is `hex:` followed by exactly 64 lowercase hexadecimal digits. Share 1 is `b64:` followed by canonical padded standard base64 for exactly 32 bytes. Share 2 is `b64url:` followed by canonical unpadded base64url for exactly 32 bytes. XOR the three decoded 32-byte shares to obtain the input key material.

The 64-byte key schedule output is HKDF-SHA256 with:

- input key material: the XOR result;
- salt: SHA-256 of UTF-8 `PFSEAL2`, one NUL byte, the workspace id, one NUL byte, then the work-pool name;
- info: UTF-8 `prefect-seal/deployment/{deployment_id}/key/{V}`.

Bytes 0 through 31 of the output are `encKey`; bytes 32 through 63 are `macKey`. Identifiers are used exactly as stored, without trimming, case folding, or Unicode normalization.

## Key-set witness attestation

Before evaluating retired/future policy or authenticating the envelope, verify the effective key set against `pfseal_key_witnesses`. The attestation metadata value is canonical minified key-sorted JSON with exactly `revision` and `signatures`. `revision` is a JavaScript-safe non-negative integer equal to the effective database revision of the attestation row. `signatures` is an array of two or three objects, sorted strictly by `witnessId`; each object has exactly string fields `signature` and `witnessId`, and witness ids match `^[a-z][a-z0-9-]{0,31}$` without duplicates. `signature` is canonical padded standard base64 for exactly 64 bytes.

Compute `shareDigests` as the lowercase SHA-256 hex digests of decoded share 0, share 1, and share 2 in that order. The signed statement is canonical JSON containing exactly `deploymentId`, `keyVersion`, `revision`, `shareDigests`, `workPool`, and `workspaceId`. The signed bytes are UTF-8 `PFSEAL2-KEYSET-V1\n` followed by that canonical JSON. Each listed witness must resolve to exactly one row for the deployment, its `public_key_spki_b64` must be canonical padded standard base64 containing an Ed25519 SubjectPublicKeyInfo DER key, `valid_from_revision <= revision <= valid_through_revision`, and `revoked_at_revision` must be null or strictly greater than `revision`. All revision bounds must be JavaScript-safe non-negative integers with a nonempty interval. Verify every listed Ed25519 signature over the signed bytes and require at least two valid distinct witnesses. Any attestation JSON, witness row, eligibility, key, ordering, or signature error is `KEY_ATTESTATION`; an unsafe witness revision is a fatal database error.

The audit field `key_attestation_sha256` is lowercase SHA-256 over the exact UTF-8 bytes of the canonical attestation metadata value. It is included as `keyAttestationSha256` in the canonical audit-chain record.

For a readable key version below the deployment's active version, effective metadata must also contain `pfseal.key.v{V}.successor`. Its canonical value is `v{A}:` followed by lowercase hex of `HMAC-SHA256(macKey, lineageMessage)`, where `{A}` is the active version and `lineageMessage` is UTF-8 `PFSEAL2-ROTATE`, one NUL, deployment id, one NUL, `{V}`, one NUL, `{A}`, one NUL, then the decimal job metadata revision. A missing, malformed, wrong-target, or mismatched proof is a key-lineage failure. Current, retired, and future versions do not consume a lineage proof.

The audit `header_sha256` is lowercase SHA-256 hex over the complete 58-byte authenticated header (`headerCore || headerHmac`); `plaintext_sha256` is lowercase SHA-256 hex over the authenticated plaintext bytes.

## Plaintext

Authenticated plaintext is UTF-8 canonical JSON: object keys are sorted by Unicode code point, there is no insignificant whitespace, and JSON strings/numbers use `JSON.stringify` spelling. The top-level object has exactly seven keys: `deploymentId`, `expiresAt`, `issuedAt`, `notBefore`, `rotationCounter`, `secretName`, and `value`. All but `rotationCounter` are strings; the counter is a safe non-negative integer.

`deploymentId` must equal the job deployment, `secretName` must match `^[A-Z][A-Z0-9_]{0,63}$`, and all three timestamps must be canonical UTC RFC 3339 with milliseconds. They must satisfy `issuedAt <= notBefore < expiresAt`. The worker's effective `--at` time must be at or after `notBefore` and strictly before `expiresAt`. For each `(deploymentId, secretName)`, `rotationCounter` must be strictly greater than the last successful value in `prefect_secret_state`; state changes only in the successful finalization transaction. Empty secret values are permitted. Secret `value` is used only for authentication and must not be persisted or emitted.
