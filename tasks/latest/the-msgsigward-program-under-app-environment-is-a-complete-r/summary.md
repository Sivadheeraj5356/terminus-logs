# The `msgsigward` program under /app/environment is a complete RFC 9421 HTTP

- **UUID:** `4e2fdfd9-59a3-4e50-b513-c2300b5e2399`
- **Slug:** `the-msgsigward-program-under-app-environment-is-a-complete-r`
- **Category:** security
- **Difficulty:** hard

## Summary

The `msgsigward` program under /app/environment is a complete RFC 9421 HTTP message-signature verifier: `msgsig.Verify` in /app/environment/internal/msgsig/verify.go reads one immutable request bundle and prints the decision line `<verdict> <selector> <covered>` an HTTP server uses before acting on a signed request. The implementation is finished and builds, but it is **not** faithful to its specification: it contains several planted security defects, each a divergence from /app/environment/docs/security-spec.md that lets a forged, under-covered, replayed, body-substituted, or algorithm-downgraded request through — or misreports which rejection applies.

The evidence is immutable: audit the code against the spec; do not modify the verifier or the tests. Your deliverable is /app/environment/findings.json.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
