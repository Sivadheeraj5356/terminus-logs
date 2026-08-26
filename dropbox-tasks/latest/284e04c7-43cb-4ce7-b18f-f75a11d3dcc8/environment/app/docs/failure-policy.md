# Public failure precedence

Per-job failures are stable public codes. Evaluation stops at the first applicable stage in this order:

| Stage | Code | Conditions |
| ---: | --- | --- |
| 1 | `ENVELOPE_FORMAT` | image/label JSON errors, invalid direct/chunk transport, noncanonical base64, invalid magic/flags/version/length |
| 2 | `KEY_METADATA` | missing deployment, revision outside its policy window, inconsistent deployment policy, or missing/malformed effective metadata |
| 3 | `KEY_ATTESTATION` | malformed or noncanonical key-set attestation, invalid/duplicate/ineligible witness, bad Ed25519 signature, or fewer than two valid witnesses |
| 4 | `KEY_RETIRED` | envelope version below `minimum_readable_key_version` |
| 5 | `KEY_FUTURE` | envelope version above `active_key_version` |
| 6 | `KEY_LINEAGE` | missing, malformed, wrong-target, or mismatched successor proof for a rotation |
| 7 | `AUTH_HEADER` | header HMAC mismatch |
| 8 | `AUTH_GCM` | GCM authentication or decryption failure |
| 9 | `PAYLOAD_INVALID` | invalid UTF-8, JSON, canonical encoding, fields, binding, or internal timestamp order |
| 10 | `PAYLOAD_NOT_YET_VALID` | effective worker time is before `notBefore` |
| 11 | `PAYLOAD_EXPIRED` | effective worker time is at or after `expiresAt` |
| 12 | `PAYLOAD_REPLAY` | counter is not strictly greater than successful state for the deployment and secret |

A valid older key at or above the minimum produces rotation decision `rotate`; an envelope at the active version produces `current`. No other successful decision exists.
