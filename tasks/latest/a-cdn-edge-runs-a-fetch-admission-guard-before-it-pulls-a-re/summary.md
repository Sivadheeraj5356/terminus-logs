# A CDN edge runs a fetch-admission guard: before it pulls a resource from an upst

- **UUID:** `512da6e5-bd97-4ca4-87aa-8576ac4a731d`
- **Slug:** `a-cdn-edge-runs-a-fetch-admission-guard-before-it-pulls-a-re`
- **Category:** security
- **Difficulty:** hard

## Summary

A CDN edge runs a fetch-admission guard: before it pulls a resource from an upstream, it checks the request against the route's allowlist and either admits the fetch or blocks it. Leave the check too loose and an attacker slips an injected `data:` script or a look-alike host such as `evil.example.com.attacker.com` past the allowlist, and the smuggled content runs; make it too strict and the guard drops assets the site legitimately serves.

The guard in the Go sources at `/app` makes exactly this allow-or-block decision. It is handed the allowlist attached to a route (the raw value of a Content-Security-Policy directive such as `script-src`), the candidate resource URL, and the page's own origin, and answers whether that fetch is admitted.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
