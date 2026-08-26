# CT-style transparency-log entry — submission format note

This note describes the **wire shape** of a transparency-log entry as it arrives
on the submission API. It is a field reference for operators. It deliberately
does **not** specify the leaf-canonicalization algorithm (how an entry is reduced
to the bytes the log hashes and signs) — that lives in the signer and is recovered
from the worked examples shipped alongside this note.

## Entry object

A submitted entry is a JSON object. Observed fields:

| field         | type             | notes                                            |
| ------------- | ---------------- | ------------------------------------------------ |
| `log_id`      | string           | the log shard identifier                         |
| `index`       | integer          | the 0-based leaf index assigned by the log       |
| `leaf_type`   | string           | `x509_entry` or `precert_entry`                  |
| `issuer_id`   | string           | identifier of the issuing CA (often present)     |
| `subject`     | string \| list   | one or more DNS subject names for the leaf cert  |
| `issued_at`   | RFC3339 string   | when the certificate was issued                  |
| `payload`     | string           | the opaque certificate body                      |
| `received_at` | RFC3339 string   | when the **front-end** received the submission   |
| `x_*`         | any              | operator extension fields (free-form)            |
| `audit`       | object           | internal review bookkeeping                      |

Notes from operations:

- `subject` may be a single string or a list; lists can contain wildcard names
  (`*.example.com`), internationalized names with non-ASCII labels
  (e.g. `café.example.com`), the same name in different letter case, and a name
  together with one of its parent or child zones.
- `issued_at` is RFC3339 and **may or may not** carry a fractional-seconds part;
  both forms are seen in the wild for the same logical instant.
- `issuer_id` carries the issuing CA's identifier. Front-ends attach it to most
  submissions regardless of `leaf_type`.
- `received_at`, the `x_*` extension fields, and the `audit` block are added by
  the front-end / operators for routing and bookkeeping. They are **not** part of
  the certificate and different front-ends fill them in differently; `x_origin`
  in particular records the ingest shard that accepted the submission.
- `index` is the leaf position; the log assigns it.

## Leaf bytes, leaf hash, signed input

The log reduces each entry to a fixed **canonical byte string** (the "leaf
bytes"), takes its SHA-256 (the "leaf hash"), and the log's Ed25519 key produces
a signature. The worked examples ship, for each entry:

- `canonical_b64` — the exact canonical leaf bytes (base64),
- `canonical_sha256` — their SHA-256,
- `payload_hash_input_b64` — the exact byte string that was hashed to obtain the
  `payload` field's value inside the canonical bytes (base64); its SHA-256 is the
  hex that appears for `payload` in `canonical_b64`,
- `leaf_hash_hex` — the leaf hash,
- `signed_input_b64` — the exact bytes the Ed25519 key signed,
- `signature_b64` — a valid signature you can verify with `log_public_key.json`.

The canonical leaf bytes begin with an ASCII domain tag and are **not** a JSON
re-serialization of the entry. The exact projection, field order, value
encodings, and framing are intentionally left to be recovered from the examples.
