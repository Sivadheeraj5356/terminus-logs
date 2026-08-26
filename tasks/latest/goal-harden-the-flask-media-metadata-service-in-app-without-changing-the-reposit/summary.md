# ## Goal

- **UUID:** `be063bdd-bdaa-4b0b-86dc-11f74f61b7b2`
- **Slug:** `goal-harden-the-flask-media-metadata-service-in-app-without-changing-the-reposit`
- **Category:** security
- **Difficulty:** hard

## Summary

Harden the Flask media metadata service in `/app` without changing the repository root layout. The finished project is an offline build-and-report pipeline: it must not download anything, it must not trust a system `yq`, and `make report PORT=<port>` must generate `build/hardened-report.json` from the current fixtures, manifest, and live local API responses rather than from hard-coded values.

Run Flask only on localhost with debug disabled. Allow CORS only for `https://media.example.test`, return `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`, and never expose absolute fixture paths.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
