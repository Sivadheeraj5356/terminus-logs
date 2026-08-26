# Archive input format

Load archive_*.json from /app/archives unless EBTA_ARCHIVES_DIR points at another directory.
Only analyze archive_01.json through archive_20.json by archive_id. Ignore other archive_*.json files.

Each archive file:

```
{
  "archive_id": "archive_XX",
  "objects": [
    {
      "id": "O1",
      "key_id": "K1",
      "cipher": "AES-256-GCM",
      "content_digest": "hex",
      "declared_digest": "hex"
    }
  ],
  "keys": [
    {
      "id": "K1",
      "role": "data" | "escrow",
      "algorithm": "AES-256-GCM",
      "state": "active" | "revoked" | "destroyed",
      "rewrap_needed": bool,
      "rewrap_token": string,
      "threshold": int,
      "shares": [
        {"id": "S1", "fingerprint": "fp", "revoked": bool}
      ]
    }
  ],
  "escrow": {
    "registered_fingerprints": {"K1": ["fp1", "fp2"]}
  },
  "manifest": {
    "signed_digests": ["hex"]
  },
  "recovery": {
    "path_count": int,
    "requires_online_hsm": bool,
    "offline_cold_share": bool,
    "geographic_split": bool
  },
  "retention": {
    "declared_days": int,
    "enforced_days": int,
    "immutable": bool,
    "legal_hold": bool
  },
  "restore": {
    "chain_ok": bool,
    "signer": string,
    "nonce_reuse": bool
  },
  "shards": [
    {"id": "P1", "declared_crc": "c1", "payload_crc": "c1"}
  ],
  "expected_shards": int,
  "adversary_tests": [
    {"id": "T1", "surviving": bool}
  ]
}
```

## Finding emission rules

coverage_gap: object.cipher is empty, none, plaintext, or not listed in ciphers.approved.
unauthorized_mutation: content_digest != declared_digest, or content_digest missing from manifest.signed_digests.
escrow_break: for role escrow keys, count non-revoked shares whose fingerprint is registered; break when that count is below max(escrow.min_quorum, key.threshold).
recovery_weakness: path_count < 2 and requires_online_hsm is true, unless offline_cold_share or geographic_split is true.
retention_tamper: immutable is false while retention.requires_immutable is true, or enforced_days < declared_days. Suppress both when legal_hold is true and enforced_days >= declared_days.
recovery_guarantee_fail: an object references a key whose state is revoked or destroyed, or whose rewrap_needed is true with an empty rewrap_token.
stale_dependency: object.cipher is in ciphers.stale, or key.algorithm is in algorithms.stale. Emit one finding per subject.
restore_forgery: nonce_reuse is true, or chain_ok is false, or signer is not in restore.trusted_signers.
silent_corruption: any shard declared_crc != payload_crc, or expected_shards != len(shards).
resilience_fail: one finding per adversary_tests entry with surviving false. Empty adversary_tests emits nothing.

archive_id must match the filename stem.
