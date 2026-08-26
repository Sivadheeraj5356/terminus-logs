# Dual-control settlement rotation contract

This file is part of the public task contract. The words **must**, **must not**, and **exactly** are normative.

## CLI and policy

`/app/bin/rotate_ceremony` accepts no positional arguments. Its only options are `--policy PATH` and `--output PATH`, each exactly once and each followed by a value. Their defaults are `/app/ceremony/policy.json` and `/app/ceremony/rotation-attestation.json`. Unknown, repeated, or incomplete options are errors.

The policy is a JSON object with this exact shape; no shown object may contain additional or missing members:

```json
{
  "schema": "settlement-key-rotation-v2",
  "primary_token": {"label": "...", "user_pin": "..."},
  "escrow_token": {"label": "...", "user_pin": "..."},
  "epoch": "...",
  "retiring": {
    "id": "...",
    "private_label": "...",
    "certificate_label": "..."
  },
  "active": {
    "id": "...",
    "private_label": "...",
    "certificate_label": "...",
    "private_key_path": "/absolute/path.pem",
    "certificate_path": "/absolute/path.pem",
    "allowed_mechanism": "SHA256-RSA-PKCS"
  },
  "recovery": {
    "id": "...",
    "label": "...",
    "bytes": 32,
    "allowed_mechanism": "AES-KEY-WRAP"
  },
  "escrow": {
    "id": "...",
    "private_label": "...",
    "certificate_label": "...",
    "key_wrap_mechanism": "RSA-PKCS-OAEP-SHA1"
  },
  "envelope": {
    "object_id": "...",
    "label": "...",
    "application": "settlement-recovery-envelope-v2",
    "cipher": "AES-256-GCM"
  },
  "continuity": {
    "object_id": "...",
    "label": "...",
    "application": "settlement-rotation-continuity-v2"
  },
  "receipt": {
    "object_id": "...",
    "label": "...",
    "application": "settlement-escrow-receipt-v2"
  }
}
```

The JSON text must not contain duplicate member names. Every shown string must be nonempty and contain neither carriage return nor newline. The seven identifiers `retiring.id`, `active.id`, `recovery.id`, `escrow.id`, `envelope.object_id`, `continuity.object_id`, and `receipt.object_id` must be pairwise distinct lowercase even-length hexadecimal strings representing 1 through 32 raw bytes. The ten object labels must be pairwise distinct, and the two token labels must differ. Both input paths must be absolute. The fixed schema, mechanism, application, cipher, and byte-count values shown above are the only supported values.

The incoming certificate path is always required and must contain one PEM X.509 certificate with an RSA public key of at least 2048 bits. When the staged private-key path exists it must contain one unencrypted RSA PEM private key of at least 2048 bits that matches the certificate. If the staged key and a recovery envelope both exist, both must resolve to that same certificate key. The certificate remains on disk; the staged private key is removed only after a successful commit.

Use the module `/usr/lib/softhsm/libsofthsm2.so` and the SoftHSM configuration already named by `SOFTHSM2_CONF`. Exactly one initialized token must exist for each policy token label. Reinitializing a token, clearing the token directory, changing a PIN, or copying either token store is forbidden.

## Canonical recovery envelope

Hash the incoming certificate's DER bytes with SHA-256. Construct this exact UTF-8 additional-authenticated-data value, substituting policy strings and the lowercase 64-character certificate digest. It ends with the displayed final newline and contains no carriage returns or extra spaces.

```text
settlement-recovery-envelope-v2
epoch=<epoch>
primary_token_label=<primary_token.label>
escrow_token_label=<escrow_token.label>
active_key_id=<active.id>
recovery_key_id=<recovery.id>
escrow_key_id=<escrow.id>
active_certificate_sha256=<digest>
```

When no envelope exists, obtain a fresh unpredictable 32-byte recovery key and a fresh unpredictable 12-byte nonce. Serialize the staged active private key as unencrypted PKCS#8 DER. Encrypt that DER with AES-256-GCM under the recovery key, the 12-byte nonce, and the exact additional-authenticated-data bytes; `encrypted_private_key_base64` contains the ciphertext followed by the 16-byte GCM tag as returned by the standard AES-GCM one-shot operation. Encrypt the 32-byte recovery key to the RSA public key in the escrow token certificate using RSAES-OAEP with SHA-1 for both the OAEP digest and MGF1, and an empty label. The compatibility-specific name `RSA-PKCS-OAEP-SHA1` refers exactly to those parameters.

Serialize one envelope JSON object with exactly these keys in this order, UTF-8 encoding, `ensure_ascii=true`, separators `,` and `:` with no whitespace, and one final newline:

```json
{"schema":"settlement-recovery-envelope-v2","aad_sha256":"<lowercase SHA-256 of exact AAD>","nonce_base64":"<standard padded base64>","wrapped_recovery_key_base64":"<standard padded base64>","encrypted_private_key_base64":"<standard padded base64>"}
```

Store those exact serialized bytes in one public primary-token `CKO_DATA` object whose `CKA_OBJECT_ID`, `CKA_LABEL`, and `CKA_APPLICATION` come from `envelope`; `CKA_PRIVATE` must be false. An existing envelope is reusable only if its exact JSON encoding, hashes, base64, lengths, OAEP decryption, AES-GCM authentication, PKCS#8 decoding, and certificate-key relationship all validate. OAEP decryption must be performed by the escrow token private key rather than a filesystem copy. The recovered 32 bytes are the only permissible value of the primary token recovery key. Do not replace a malformed or undecryptable envelope.

## Canonical continuity and escrow receipt

Hash the exact serialized envelope bytes with SHA-256. Construct the exact continuity payload below. It ends with the displayed final newline.

```text
settlement-rotation-continuity-v2
epoch=<epoch>
retiring_key_id=<retiring.id>
active_key_id=<active.id>
active_certificate_sha256=<active certificate DER digest>
recovery_envelope_sha256=<exact envelope digest>
```

Sign the continuity payload with the retiring primary-token private key using `CKM_SHA256_RSA_PKCS`. Store the raw signature bytes, not text, in one public primary-token `CKO_DATA` object whose object ID, label, and application come from `continuity`. The signature must verify against the retiring certificate stored in the primary token.

Hash the raw continuity signature with SHA-256 and construct this exact escrow-receipt payload with a final newline:

```text
settlement-escrow-receipt-v2
epoch=<epoch>
primary_token_label=<primary_token.label>
escrow_token_label=<escrow_token.label>
escrow_key_id=<escrow.id>
continuity_signature_sha256=<raw continuity signature digest>
recovery_envelope_sha256=<exact envelope digest>
```

Sign the receipt payload with the escrow-token private key using `CKM_SHA256_RSA_PKCS`. Store the raw signature bytes in one public primary-token `CKO_DATA` object whose object ID, label, and application come from `receipt`. It must verify against the escrow certificate stored in the escrow token. Existing valid envelope, continuity, and receipt bytes must be reused exactly across every rerun.

## Committed token state

Policy key IDs map to raw `CKA_ID` bytes. Evidence object IDs map to raw `CKA_OBJECT_ID` bytes. On success, the primary managed namespace contains:

* exactly one public retiring `CKO_CERTIFICATE` with the retiring ID and certificate label, and no retiring `CKO_PRIVATE_KEY`;
* exactly one active `CKO_PRIVATE_KEY` and one public active `CKO_CERTIFICATE`, both with the active ID and their respective labels;
* exactly one recovery `CKO_SECRET_KEY` with the recovery ID and label; and
* exactly one public `CKO_DATA` object for each of the envelope, continuity signature, and escrow receipt.

The escrow managed namespace remains exactly one RSA `CKO_PRIVATE_KEY` and one public X.509 `CKO_CERTIFICATE`, both with the escrow ID and their respective labels. The private key must be sensitive, non-extractable, capable of `CKM_RSA_PKCS_OAEP` decryption and `CKM_SHA256_RSA_PKCS` signing, and must prove its relationship to the certificate through the envelope decryption and receipt signature. The ceremony must not create, destroy, or modify any persistent object in the escrow token.

The active private key must be an RSA token object with `CKA_PRIVATE=true`, `CKA_SENSITIVE=true`, `CKA_EXTRACTABLE=false`, `CKA_SIGN=true`, and `CKA_SIGN_RECOVER`, `CKA_DECRYPT`, `CKA_UNWRAP`, and `CKA_DERIVE` false. Its `CKA_ALLOWED_MECHANISMS` must allow exactly `CKM_SHA256_RSA_PKCS`; an attempted `CKM_RSA_PKCS` signature must be rejected. A SHA-256 RSA PKCS#1 signature made with it must verify against the active token certificate.

The recovery object must contain the exact 32 bytes recovered from the envelope and have `CKA_TOKEN=true`, `CKA_PRIVATE=true`, `CKA_SENSITIVE=true`, `CKA_EXTRACTABLE=false`, and `CKA_WRAP=true`. `CKA_UNWRAP`, `CKA_ENCRYPT`, `CKA_DECRYPT`, `CKA_SIGN`, `CKA_VERIFY`, and `CKA_DERIVE` must be false. Its `CKA_ALLOWED_MECHANISMS` must allow exactly `CKM_AES_KEY_WRAP`. Because its value is unreadable, validate its envelope binding by wrapping a known temporary non-token AES probe with `CKM_AES_KEY_WRAP` and unwrapping that result in memory with the recovered envelope key. Temporary session probes are permitted; persistent probe objects are not.

An unauthenticated auditor must be able to enumerate and read the retiring, active, and escrow certificates and all three evidence data objects on their respective tokens. Private and secret objects must not be exposed without login. Objects outside the seven policy identifiers and all objects whose labels are outside the ten policy labels are unmanaged and must remain byte-for-byte usable. The ceremony must not create extra persistent objects, including artifacts with an empty or unexpected identifier or label.

## Reconciliation and failure safety

Derive progress exclusively from both live token states and the current policy. Before the retiring private key is destroyed, a valid envelope, continuity signature, escrow receipt, active key and certificate, and envelope-bound recovery key must all exist and pass the complete final checks. Destroy the retiring private key only as the last persistent token mutation. No persistent escrow-token mutation is permitted.

An existing managed object may be reused only when its class, identifier, label, public/private status, value or key relationship, security attributes, mechanism restriction, and cross-token cryptographic binding match this contract. Before making any persistent mutation, inventory both tokens and validate every existing managed object. Missing objects may then be created in this order: envelope, continuity, receipt, active certificate, active private key, recovery key. A crash after any completed creation may leave a valid partial state; a later invocation must reuse the durable bytes and continue.

A valid envelope permits reconstruction of the active private key and the recovery-key value even when the staged private key is absent. A missing envelope requires the staged private key. A missing continuity object requires the retiring private key. A missing receipt requires the escrow private key. A committed state with no retiring private key and no staged private key must succeed when every final object validates.

Fail before persistent mutation if the policy or present staged material is invalid; either token is absent, ambiguous, or cannot authenticate; a managed identifier or label has a duplicate or conflicting object; an existing managed object or evidence chain is invalid; an existing active or recovery key does not match the envelope; or the missing evidence cannot be reconstructed. If both the retiring private key and valid continuity evidence are absent, or both the staged private key and valid recovery envelope are absent while replacement material is missing, the state is irrecoverable and must fail. Do not replace bad evidence, regenerate a valid existing envelope or recovery key, delete conflicts, or guess that a rotation completed. These preflight failures must preserve all persistent objects on both tokens and preserve the staged private key.

Remove the requested output before reading the policy. On every error, return nonzero, keep that output absent, and emit a nonempty stderr diagnostic whose first text is `rotate_ceremony:`. Write the final output atomically only after final live-token validation and staged-key removal succeed.

## Attestation

The output must be one JSON object with exactly these top-level fields and a trailing newline:

```json
{
  "schema": "settlement-rotation-attestation-v2",
  "primary_token_label": "<primary_token.label>",
  "escrow_token_label": "<escrow_token.label>",
  "epoch": "<epoch>",
  "retiring_key_id": "<retiring.id>",
  "active_key_id": "<active.id>",
  "recovery_key_id": "<recovery.id>",
  "escrow_key_id": "<escrow.id>",
  "envelope_object_id": "<envelope.object_id>",
  "continuity_object_id": "<continuity.object_id>",
  "receipt_object_id": "<receipt.object_id>",
  "retiring_certificate_sha256": "<lowercase SHA-256 of retiring primary-token certificate DER>",
  "active_certificate_sha256": "<lowercase SHA-256 of active primary-token certificate DER>",
  "escrow_certificate_sha256": "<lowercase SHA-256 of escrow-token certificate DER>",
  "recovery_envelope_sha256": "<lowercase SHA-256 of exact envelope object bytes>",
  "continuity_payload_sha256": "<lowercase SHA-256 of exact continuity payload bytes>",
  "receipt_payload_sha256": "<lowercase SHA-256 of exact receipt payload bytes>",
  "continuity_signature_base64": "<standard padded base64 of raw continuity CKA_VALUE>",
  "escrow_receipt_signature_base64": "<standard padded base64 of raw receipt CKA_VALUE>"
}
```

Every fingerprint, signature, identifier, and token label must be derived from the verified live objects and current policy rather than copied from a previous output.
