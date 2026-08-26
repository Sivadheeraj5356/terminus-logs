# Debian and Ubuntu platform operators keep auditd-style rule stacks and

Submission: `b6e42b2b-ebf0-4a16-90fb-b9a2599aa360`  
Slug: `debian-and-ubuntu-platform-operators-keep-auditd-style-rule-`  
Latest archive: `b6e42b2b-ebf0-4a16-90fb-b9a2599aa360_submission_2026-07-18T13_59_04.712Z.zip`  
Revisions in Dropbox: 1

## Task summary

Debian and Ubuntu platform operators keep auditd-style rule stacks and augenrules-style tier merges next to host audit policy. Host audit flavor is in /app/environment/etc/audit/auditd.conf, with rule-include flavor under /app/environment/etc/audit/rules.d/. After ordinary rule reloads, a second reload cycle, or a syscall-class revoke, a bundled local readiness check can still report convergence while regenerated lineage under /app/output shows missing syscall classes, conflicting generation markers, or dropped rows that were previously accepted in the enforced view. Bring the host audit rule-reload and lineage path under /app/environment into line so /app/bin/arctl reload --profile <name> and /app/bin/arctl inspect --profile <name> regenerate /app/output/rule_lineage.json through the normal operator pipeline. Hand-written output, static JSON drops, test edits, and wrapper-only bypasses are rejected. The verifier may delete that artifact, disturb durable state, and rerun the operator commands.

Required artifacts include: `/app/environment/etc/audit/auditd.conf`, `/app/environment/etc/audit/rules.d/`, `/app/output`, `/app/environment`, `/app/bin/arctl`, `/app/output/rule_lineage.json`, `/app/environment/store/ledger.json`, `/app/environment/docs/overview.md`.

Author anonymous tagged this **hard** system-administration task (linux, debian, auditd, audit-rules, augenrules, rule-reload).

Time estimates: expert ~45 min, junior ~150 min.

Harbor timeouts: agent 1200s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `b6e42b2b-ebf0-4a16-90fb-b9a2599aa360_submission_2026-07-18T13_59_04.712Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
