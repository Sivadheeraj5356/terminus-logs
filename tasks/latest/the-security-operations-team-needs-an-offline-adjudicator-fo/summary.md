# The security operations team needs an offline adjudicator for signed emergency b

- **UUID:** `357dea52-1def-4f5d-a0b9-228e60de1124`
- **Slug:** `the-security-operations-team-needs-an-offline-adjudicator-fo`
- **Category:** security
- **Difficulty:** hard

## Summary

The security operations team needs an offline adjudicator for signed emergency break-glass access events. It must verify authorization-event signatures, reconstruct privileged session state, apply gateway lock state, quorum, separation-of-duty, control-window, token-replay, and risk rules, then write the exact access-control adjudication report.

Implement the Go access-control adjudicator at `/workspace/cmd/breakglass-ledger/main.go` and build the executable at `/workspace/bin/breakglass-ledger`. The runtime is offline.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
