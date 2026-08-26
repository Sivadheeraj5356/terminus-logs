# Maven reactor packaging workspace under /app. Local assemble-check stays green,

- **UUID:** `2cd5db6c-dfb6-4b38-abc7-7433d24199e4`
- **Slug:** `maven-reactor-packaging-workspace-under-app-local-assemble-c`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Maven reactor packaging workspace under /app. Local assemble-check stays green, yet /app/output/ffm_ledger.json still shows per-classifier native jar bindings and module-path lane assignments disagreeing with the toolchain pin table once scenario packs vary host architecture, secondary toolchain, and classpath versus module-path jar presence.

The reactor is offline and processes every pack under /app/data/scenarios. Drive /app/bin/reactor across the scenario packs so every ledger row is coherent.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
