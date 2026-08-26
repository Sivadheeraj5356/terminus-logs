# Night cutover left the PAM auth fabric under /app disagreeing with itself. /app/

Submission: `e0bb6423-aadd-4c9b-8b66-7b77a721ebeb`  
Slug: `night-cutover-left-the-pam-auth-fabric-under-app-disagreeing`  
Latest archive: `e0bb6423-aadd-4c9b-8b66-7b77a721ebeb_submission_2026-07-16T14_36_22.947Z.zip`  
Revisions: 1

## Task summary

Night cutover left the PAM auth fabric under /app disagreeing with itself. /app/scripts/stack_probe.sh prints CLEAN, but replaying the pack through /app/tools/auth_tape_replay (which drives /app/bin/pam_audit) still produces wrong lockout totals, wrong stack bindings on mixed-service conversations, expired principals reading active, and non-counted module noise inflating faillock. Signed desk tip packets under /app/data/corp are the authoritative polarity source. Cutover left /app/ctl planes, /app/rt defaults, and durable tallies under /app/var/tally out of sync with that tip; /app/docs/operations.md states durable ledger hygiene against the signed carry tip. Rebuild with /app/scripts/build.sh, replay /app/config/default_pack.json, and publish /app/output/pam_lockout_report.json. The report needs ordered audits plus summary. Each audit carries conversation_id, lockout_active, retry_count, expired_account, stack_binding, binding_rows, and digest_hex. binding_rows use canon_actor, module_tag, bound, and reason. Summary carries pack_ok, audited_count, and total_lockouts. Rebuild and replay — pasted JSON will not match.

Required artifacts include: `/app/scripts/stack_probe.sh`, `/app/tools/auth_tape_replay`, `/app/bin/pam_audit`, `/app/data/corp`, `/app/ctl`, `/app/rt`, `/app/var/tally`, `/app/docs/operations.md`.

Author anonymous tagged this **hard** security task (pam, faillock, authentication, authority, lockout).

Time estimates: expert ~90 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `e0bb6423-aadd-4c9b-8b66-7b77a721ebeb_submission_2026-07-16T14_36_22.947Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
