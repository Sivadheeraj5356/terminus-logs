# Linux PAM faillock-style account lockout under `/app` is meant to stop credentia

Submission: `b235616e-3a53-493c-b0b4-ba479a1846ad`  
Slug: `linux-pam-faillock-style-account-lockout-under-app-is-meant`  
Latest archive: `b235616e-3a53-493c-b0b4-ba479a1846ad_submission_2026-07-16T12_10_23.677Z.zip`  
Revisions: 1

## Task summary

Linux PAM faillock-style account lockout under `/app` is meant to stop credential stuffing and brute-force password attacks against principals. Access decisions are judged from a host management view and from a separated user-namespace privilege boundary: a principal locked out on the host must also be denied inside the namespace, and the reverse. After realistic attack traffic — burst failed logins, grace-hold expiry, out-of-order compensating unlocks, enforce suspend/resume, principal switches, truncated auth-event tails, and separate controller invocations across restarts — lockout denials, unlocked access, and failure tallies drift between those views. Namespace privilege boundaries no longer match host-side authentication enforcement, so principals locked on the host can still authenticate in the namespace (and the reverse). Restore PAM authentication lockout integrity so host and namespace views agree on who is locked, deny paths stay consistent across privilege boundaries, and the security audit surfaces in `/app/output/lock_ledger.json` and `/app/output/lock_audit.json` reflect live auth-store enforcement rather than hand-authored JSON. The graded access-control binary is `/app/bin/bayctl`. Lockout attack scenarios live under `/app/data/scenarios/`; failed-login and unlock records live under `/app/data/batches/`. Lockout thresholds, unlock semantics, grace-hold expiry, legacy tally merge, and digest rules are defined in `/app/docs/lock_rules.md` and `/app/docs/lock_contract.md`. When starter code disagrees with those documents or this note, this note wins.

Required artifacts include: `/app/output/lock_ledger.json`, `/app/output/lock_audit.json`, `/app/bin/bayctl`, `/app/data/scenarios/`, `/app/data/batches/`, `/app/docs/lock_rules.md`, `/app/docs/lock_contract.md`, `/app/data/legacy/tally_v0.json`.

Author anonymous tagged this **hard** security task (security, pam, faillock, authentication, account-lockout, linux-auth).

Time estimates: expert ~300 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `b235616e-3a53-493c-b0b4-ba479a1846ad_submission_2026-07-16T12_10_23.677Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
