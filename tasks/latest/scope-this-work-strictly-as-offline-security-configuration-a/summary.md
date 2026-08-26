# Scope this work strictly as offline security configuration and incident response

- **UUID:** `74c48223-9690-4a43-bfd6-ca88fe4a01ae`
- **Slug:** `scope-this-work-strictly-as-offline-security-configuration-a`
- **Category:** security
- **Difficulty:** hard

## Summary

Scope this work strictly as offline security configuration and incident response for a factory StreamVault NVR. The deliverable is a remediated deployment bundle—not an application feature, API, library, service endpoint, or reusable software product.

Recover the export under `/workspace/streamvault/input` using the supplied administrative recovery hook at `/workspace/streamvault/src/harden.mjs`; its audited invocation accepts `--fleet-db`, `--runbook`, `--input`, and `--output`. Compliance records must show real use of the host's approved `sqlite3`, `jq`, `yq`, and `sha256sum` commands for registry access, configuration normalization, YAML handling, and bundle checksums.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
