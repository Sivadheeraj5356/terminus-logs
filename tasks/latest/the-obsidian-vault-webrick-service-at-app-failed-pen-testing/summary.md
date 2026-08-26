# The Obsidian Vault WEBrick service at `/app` failed pen testing against the secu

- **UUID:** `0d727b9a-6d60-407f-b486-40c70d99ceb6`
- **Slug:** `the-obsidian-vault-webrick-service-at-app-failed-pen-testing`
- **Category:** security
- **Difficulty:** medium

## Summary

The Obsidian Vault WEBrick service at `/app` failed pen testing against the security contract in `/app/docs/api_spec.md`. Incident write-ups and exploit notes live in `/app/docs/vault_design_dossier.md`.

Close the open vulnerabilities so the service matches that contract:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
