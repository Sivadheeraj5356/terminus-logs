# Report shape

`pam_lockout_report.json` has `audits` (pack order) and `summary`.

Each audit row includes conversation_id, lockout_active, retry_count,
expired_account, stack_binding, binding_rows, and digest_hex. binding_rows carry
canon_actor, module_tag, bound, and reason. Summary carries pack_ok,
audited_count, and total_lockouts.

Digest binding stays enabled when runtime opts require it; pasted JSON that was
not produced by a live rebuild/replay will not survive verification.
