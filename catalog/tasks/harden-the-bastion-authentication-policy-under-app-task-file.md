# Harden the bastion authentication policy under `/app/task_file/etc` so it is saf

Submission: `3013ca33-8490-4067-8063-7b8917597af7`  
Slug: `harden-the-bastion-authentication-policy-under-app-task-file`  
Latest archive: `3013ca33-8490-4067-8063-7b8917597af7_submission_2026-07-18T12_35_24.102Z.zip`  
Revisions: 2

## Task summary

Harden the bastion authentication policy under `/app/task_file/etc` so it is safe to promote to the real jump hosts. Work only by updating the listed configuration files in place. The target files are `/app/task_file/etc/pam.d/sshd`, `/app/task_file/etc/pam.d/sudo`, `/app/task_file/etc/pam.d/ci-deploy`, `/app/task_file/etc/security/access.conf`, `/app/task_file/etc/security/time.conf`, `/app/task_file/etc/security/faillock.conf`, `/app/task_file/etc/ssh/sshd_config`, and `/app/task_file/etc/sudoers.d/bastion`.

Required artifacts include: `/app/task_file/etc`, `/app/task_file/etc/pam.d/sshd`, `/app/task_file/etc/pam.d/sudo`, `/app/task_file/etc/pam.d/ci-deploy`, `/app/task_file/etc/security/access.conf`, `/app/task_file/etc/security/time.conf`, `/app/task_file/etc/security/faillock.conf`, `/app/task_file/etc/ssh/sshd_config`.

Author Anonymous tagged this **hard** system-administration task (pam, ssh, sudo, bastion-host, hardening).

Time estimates: expert ~120 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `3013ca33-8490-4067-8063-7b8917597af7_submission_2026-07-18T12_35_24.102Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
