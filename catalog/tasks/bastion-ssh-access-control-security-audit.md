# # Bastion SSH access-control security audit

Submission: `21eb7e86-4f41-49c0-b69c-b33ae0192f13`  
Slug: `bastion-ssh-access-control-security-audit`  
Latest archive: `21eb7e86-4f41-49c0-b69c-b33ae0192f13_submission_2026-07-11T13_01_48.840Z.zip`  
Revisions: 1

## Task summary

Security task (`security_authority_split`): enforce least-privilege jump-host posture for Redis-authoritative bastion principals. Staging at `/app/staging/bundle.tar.gz` has drifted SSH directives, sudoers grants, and home-directory permissions relative to the live access registry. Ratified authorization merge policy — principals, allowed SSH keys, sudoers fragments, `sshd_config.d` posture, and the trust boundary between live registry reads versus archive/cache shadows — lives in `/app/docs/bastion_access_handbook.md`. See `/app/docs/SECURITY_SCOPE.md` for task classification. Audit and remediation trace schemas are under `/app/contracts/`. Desk circulation drafts under `/app/docs/` are not authoritative.

Required artifacts include: `/app/staging/bundle.tar.gz`, `/app/docs/bastion_access_handbook.md`, `/app/docs/SECURITY_SCOPE.md`, `/app/contracts/`, `/app/docs/`, `/app/bastion_cli`, `/app/contracts/audit_report_schema.md`, `/app/contracts/fix_manifest_schema.md`.

Author anonymous tagged this **hard** security task (security, access-control, ssh-hardening, least-privilege, redis, bastion).

Time estimates: expert ~840 min, junior ~1560 min.

Harbor timeouts: agent 1200s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `21eb7e86-4f41-49c0-b69c-b33ae0192f13_submission_2026-07-11T13_01_48.840Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
