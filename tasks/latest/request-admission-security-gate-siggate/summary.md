# Request admission security gate (`siggate`)

- **UUID:** `5a15cc6d-691f-40c9-affa-cfb766041872`
- **Slug:** `request-admission-security-gate-siggate`
- **Category:** security
- **Difficulty:** hard

## Summary

Request admission security gate (`siggate`) ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ This is a **perimeter authentication and anti-replay security control**. At request admission, `/app/bin/siggate` must reject **forged** Harbor Request MAC v1 (HRM-1) envelopes and **replayed** authentic envelopes before traffic is admitted.

Admit/deny outcomes are security decisions under the site profile.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
