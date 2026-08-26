# Linux PAM faillock-style account lockout under `/app` is meant to stop credentia

- **UUID:** `b235616e-3a53-493c-b0b4-ba479a1846ad`
- **Slug:** `linux-pam-faillock-style-account-lockout-under-app-is-meant`
- **Category:** security
- **Difficulty:** hard

## Summary

Linux PAM faillock-style account lockout under `/app` is meant to stop credential stuffing and brute-force password attacks against principals. Access decisions are judged from a host management view and from a separated user-namespace privilege boundary: a principal locked out on the host must also be denied inside the namespace, and the reverse.

After realistic attack traffic — burst failed logins, grace-hold expiry, out-of-order compensating unlocks, enforce suspend/resume, principal switches, truncated auth-event tails, and separate controller invocations across restarts — lockout denials, unlocked access, and failure tallies drift between those views. Namespace privilege boundaries no longer match host-side authentication enforcement, so principals locked on the host can still authenticate in the namespace (and the reverse).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
