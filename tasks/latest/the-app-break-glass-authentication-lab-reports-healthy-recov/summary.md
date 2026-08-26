# The `/app` break-glass authentication lab reports healthy recovery probes yet di

- **UUID:** `49f5490e-9e2f-4905-8968-eab1f4159d0f`
- **Slug:** `the-app-break-glass-authentication-lab-reports-healthy-recov`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The `/app` break-glass authentication lab reports healthy recovery probes yet disagreeing login, session, checkpoint, and replay projections. Fix the lab sources and authored policy so the public verification workflow completes and emits `/app/reports/recovery-proof.json`.

Regenerated `/app/runtime/pam.d` stacks must track policy regeneration from source. `recovery-proof.json` carries `policy_source_sha256`, `policy_runtime_sha256`, audit counts, `state_converged`, and `collision_token` (`fresh` with main recovery token consumed in the public collision flow).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
