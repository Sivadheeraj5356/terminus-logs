# # volatile scope sweep ledger rebuild

- **UUID:** `4b6650cb-9e59-4011-928d-09eb581dd523`
- **Slug:** `volatile-scope-sweep-ledger-rebuild`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Volatile-path scope journals rotated during maintenance, and operators now see `/app/output/sweep_ledger.json`, `/app/output/probe_snapshot.json`, and `/app/state/scope_state.json` drift from the VSW1 fixtures, overlays, and profile manifests. Counts look plausible but window boundaries skew, cross-bucket sequence-gap rollups disagree, digests fail an independent roll, merge collapses distinct scope/mask pairs or scans journals with the wrong slack, and probe still reports a stale cache width or pre-overlay mask after manifest rotation.

Repair the Rust sources under `/app/environment` so the normal pipeline regenerates artifacts. Hand-written JSON, fixture edits, or wrapper-only changes are insufficient.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
