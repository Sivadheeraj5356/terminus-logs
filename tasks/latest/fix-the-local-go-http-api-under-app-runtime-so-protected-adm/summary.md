# Fix the local Go HTTP API under `/app/runtime` so protected admin endpoints requ

- **UUID:** `60daaed1-f2f7-4b33-bc95-7bbbb3ea0896`
- **Slug:** `fix-the-local-go-http-api-under-app-runtime-so-protected-adm`
- **Category:** security
- **Difficulty:** hard

## Summary

Fix the local Go HTTP API under `/app/runtime` so protected admin endpoints require a valid bearer token on every request, including normalized/encoded path variants, replay probes, and restart/recovery sequences. Build and run with the Go toolchain at `/usr/local/go/bin`.

The public routes are `GET /v1/public/ping`, `GET /v1/public/docs`, and `GET /v1/public/state` — these must stay available without authentication under all conditions. The ping endpoint returns `{"status":"ok"}`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
