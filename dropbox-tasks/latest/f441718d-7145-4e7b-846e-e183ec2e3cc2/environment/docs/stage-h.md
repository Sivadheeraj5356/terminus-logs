# Stage H — Recovery Certificate

## Body fields (canonical JSON)

- `version`: `recovery-certificate-v1`
- `workflow_id`
- `plan_digest`
- `journal_hash`
- `replay_hash` (**required binding**)
- `recovery_digest`
- `verification_hash`
- `provenance` map

## Digests

```
body_digest = DomainHash("recovery-certificate-v1", canonical_body)
signature   = hex(HMAC-SHA256(token, canonical_body))
```

Token file: `configs/hmac_signing_token.txt` (default content `workflow-runtime-hmac-token-v1`).

## Outputs

`output/certificate.json`, `output/certificate_status.json`
