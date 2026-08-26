# Harden the bastion authentication policy under `/app/task_file/etc` so it is saf

- **UUID:** `3013ca33-8490-4067-8063-7b8917597af7`
- **Slug:** `harden-the-bastion-authentication-policy-under-app-task-file`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Harden the bastion authentication policy under `/app/task_file/etc` so it is safe to promote to the real jump hosts. Work only by updating the listed configuration files in place.

The target files are `/app/task_file/etc/pam.d/sshd`, `/app/task_file/etc/pam.d/sudo`, `/app/task_file/etc/pam.d/ci-deploy`, `/app/task_file/etc/security/access.conf`, `/app/task_file/etc/security/time.conf`, `/app/task_file/etc/security/faillock.conf`, `/app/task_file/etc/ssh/sshd_config`, and `/app/task_file/etc/sudoers.d/bastion`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
