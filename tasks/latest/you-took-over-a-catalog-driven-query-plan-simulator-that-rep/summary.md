# You took over a catalog-driven query plan simulator that replays scenario tapes

- **UUID:** `92196d45-f956-4651-8d6e-e137df143ad5`
- **Slug:** `you-took-over-a-catalog-driven-query-plan-simulator-that-rep`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

You took over a catalog-driven query plan simulator that replays scenario tapes and writes a plan audit report. Uninterrupted scenarios look fine, but legs that pause and resume often drift from their continuous partners.

Join methods change, access paths flip, catalog generations disagree, and plan digests stop lining up even when the summary block still looks calm. Rebuild through /app/ci/build_and_load.sh and emit /app/output/plan_audit.json so every manifest scenario matches the independent tape replay the verifier derives from the bundled tapes.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
