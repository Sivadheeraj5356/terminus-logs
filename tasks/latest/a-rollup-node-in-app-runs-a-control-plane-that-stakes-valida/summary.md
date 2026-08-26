# A rollup node in /app runs a control plane that stakes validators, finalizes L2

- **UUID:** `601a658d-baf5-43df-ba90-de1be362db1a`
- **Slug:** `a-rollup-node-in-app-runs-a-control-plane-that-stakes-valida`
- **Category:** security
- **Difficulty:** medium

## Summary

A rollup node in /app runs a control plane that stakes validators, finalizes L2 blocks by weighted committee endorsement, bridges L1 deposits into L2 balances, and runs governance referenda with re-delegable ballots. Some safeguards no longer hold.

Probe the service as an attacker would; confirm each property and correct any that fails. A bridged deposit becomes an irreversible L2 credit only once it sits the configured confirmation depth under the L1 tip — not a block early, nor withheld once that deep.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
