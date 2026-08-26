# The gateway snapshot in `/app` contains an inert Go `main` package where its

- **UUID:** `00af3d22-15fc-4b54-ba81-3ec0858a85bb`
- **Slug:** `the-gateway-snapshot-in-app-contains-an-inert-go-main-packag`
- **Category:** security
- **Difficulty:** hard

## Summary

The gateway snapshot in `/app` contains an inert Go `main` package where its authorization engine should be. Complete that package so the resulting binary can decide a stream of service-mesh requests backed by primary macaroons and arbitrarily nested third-party discharges.

This is a stateful proof-verification problem. The implementation must rebuild the chained HMACs, bind every discharge both to the primary proof and its exact parent edge, find the globally canonical assignment of single and threshold- quorum discharge tokens, evaluate normalized request caveats, and update persistent nonce and single-use proof state in request order.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
