# The GammaSpec spectral-analysis API in `/app` is failing its scientific audit. S

- **UUID:** `709d69b2-8f2a-400c-be33-15929f107e3e`
- **Slug:** `the-gammaspec-spectral-analysis-api-in-app-is-failing-its-sc`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The GammaSpec spectral-analysis API in `/app` is failing its scientific audit. Start with `/app/docs/00_gammaspec_contract.md`; it is the short normative map for the numerical wire contract.

Treat `/app/docs/gammaspec_methods.md` as the full GammaSpec methods source when you need lab rationale or requirement IDs, and use `/app/audit/strace-gammaspec.log` plus `/app/audit/lsof-gammaspec.txt` as operational evidence. Keep the TypeScript/Express wrapper runnable from `/app` with `npm run build` and `npm start`; `/health` should return JSON with `ok: true`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
