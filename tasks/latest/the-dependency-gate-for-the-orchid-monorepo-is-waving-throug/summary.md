# The dependency gate for the Orchid monorepo is waving through things it should b

- **UUID:** `081b841a-dbb7-4af4-9459-e2c9fef3e732`
- **Slug:** `the-dependency-gate-for-the-orchid-monorepo-is-waving-throug`
- **Category:** build-and-dependency-management
- **Difficulty:** medium

## Summary

The dependency gate for the Orchid monorepo is waving through things it should be blocking. The gate is an OPA bundle at /app/policy that scores every row of the build ledger at /app/ledger/dependency_ledger.csv — most visibly, it approved a quarantined model artifact last week, and several exception clauses from the maintainer handbook were never carried into the policy correctly.

Repair the policy bundle so its decisions match the handbook under /app/docs/handbook/ — that is the authority for quarantine handling, model artifact integrity, license classes and waivers, release channels, and lockfile provenance. The handbook has been amended over the program's life, so a threshold or clause as stated in one chapter is not necessarily still in force.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
