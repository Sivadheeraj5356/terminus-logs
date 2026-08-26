# Diagnostic manufacturing planners in an IVD reagent facility must analyze availa

- **UUID:** `e790d597-2ab7-423d-972d-99b80d282b95`
- **Slug:** `diagnostic-manufacturing-planners-in-an-ivd-reagent-facility`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Diagnostic manufacturing planners in an IVD reagent facility must analyze available reagent lots against batch concentration specifications, produce the least-cost feasible blend per specification under linear constraint satisfaction with shared lot inventory depletion across the batch, and deliver a dual-price feasibility certificate with complementary slackness closure for quality audit. Implement the blendcert least-cost blend and dual-price feasibility certificate workflow under /app per the cited contracts.

Deliver the blend feasibility workflow per /app/docs/overview.md, /app/docs/concentration-bands.md, /app/docs/lot-inventory-contract.md, /app/docs/blend-solve-contract.md, /app/docs/dual-price-certificate.md, /app/docs/gap-bound-complementary-slackness.md, /app/docs/blend-feasibility-cert-contract.md, and /app/docs/blend-ledger-contract.md.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
