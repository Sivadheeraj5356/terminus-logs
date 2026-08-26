# The release security team needs an offline keyring cutover gate for one verifier

- **UUID:** `7f868c3e-bc97-4019-8745-5c03499d1340`
- **Slug:** `the-release-security-team-needs-an-offline-keyring-cutover-g`
- **Category:** security
- **Difficulty:** hard

## Summary

The release security team needs an offline keyring cutover gate for one verifier image. The staged inputs describe candidate trust bundles, issuer limits, revoked issuers, and the claims that must be preserved during the cutover.

Write `/app/keyring_cutover_gate.go`, build `/app/keyring_cutover_gate`, and run it as `/app/keyring_cutover_gate /app/input_data/request.json /app/input_data/catalog.json /app/output_data/cutover_plan.json` without modifying the inputs. Key requirements: Maximize the number of satisfied rows in `request.required_claims`.; Minimize total selected `risk`.; Minimize total selected `footprint_kb`.; Minimize the number of selected bundles..

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
