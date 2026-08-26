# This internal mTLS PKI bridge under /app/environment left a partial trust-epoch

- **UUID:** `50111c59-9816-42e5-bfe1-4b4db2c66f13`
- **Slug:** `this-internal-mtls-pki-bridge-under-app-environment-left-a-p`
- **Category:** security
- **Difficulty:** hard

## Summary

This internal mTLS PKI bridge under /app/environment left a partial trust-epoch dump at /app/corp after an authority-boundary incident. Issuance and revocation evidence, certificate and keystore material inventories, and incomplete handshake fragments must reconcile so no principal widens role or trust authority past the PKI policy in /app/docs/cq_w3.md.

Fix the Java package sources under /app/environment so a sealed trust timeline at /app/output/tl.json proves barrier-style violations stay cleared across every arm listed in /app/corp/arms.toml, including reorder_j, drop_snap, reenc_pem, perm_a, perm_b, hostile_role, base, and the alt pack arms (alt_base, alt_reorder, alt_drop, alt_perm). Digest helpers live under /app/tools/digest_pack.py; cq_w3 is the obligation home for principals, authority outcomes, revocation and handshake rules, closed fixture algebra, digest construction, and ledger field layout.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
