The `/app` break-glass authentication lab reports healthy recovery probes yet disagreeing login, session, checkpoint, and replay projections. Fix the lab sources and authored policy so the public verification workflow completes and emits `/app/reports/recovery-proof.json`. Regenerated `/app/runtime/pam.d` stacks must track policy regeneration from source.

## Recovery proof report

`recovery-proof.json` carries `policy_source_sha256`, `policy_runtime_sha256`, audit counts, `state_converged`, and `collision_token` (`fresh` with main recovery token consumed in the public collision flow).

## Lockout and recovery

Three password failures lock an account and deny further password attempts. One-use recovery opens a session for a locked account, clears the lock following session creation, and rejects replay. Recovery rejection on an occupied session leaves token and lock reset untouched. Both `auth_err` and `ignore` password non-applicable results participate in recovery. Recovery transactions journal session open ahead of lock reset.

## Policy, audit, and replay

Compiled runtime stacks mirror authored policy. Matched audit open/close pairs cover successful login/logout; failed logins lack opens. Normalized live state matches journal replay from bundled fixtures.

## Checkpoints

Checkpoint save/restore rewinds journal-backed state; duplicate restore on one label is stable.
