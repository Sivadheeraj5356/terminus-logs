# Operator contract

The login service exposes password and recovery methods. Password failures increment `faillock`; the third failure locks the account. A locked account is denied by password authentication until a complete successful login commits a reset.

A recovery token is one-use. Authentication success alone is not consumption: token consumption and lock reset belong to the successful login transaction and therefore occur only after the requested session identifier is available. Rejected recovery attempts leave both resources unchanged.

The password module has two supported non-applicable outcomes during recovery: `auth_err` for accounts backed by the legacy password provider and `ignore` for accounts delegated to an external provider. The parent stack must offer the same recovery behavior for both outcomes. Policy source is compiled into runtime stacks; compiler output must preserve the authored control flow.

A successful login emits one session-open event and a successful logout emits one matching session-close event. Materialized token, lock, session, and audit files are projections. The journal is authoritative: rebuilding projections from fixtures plus the journal must reproduce the same normalized state.

Checkpoint restore rewinds both the journal and projections to the saved label. Running restore twice with the same label must leave the lab unchanged.
