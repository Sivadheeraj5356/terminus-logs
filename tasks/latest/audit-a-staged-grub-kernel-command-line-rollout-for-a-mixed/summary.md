# Audit a staged GRUB/kernel-command-line rollout for a mixed Linux fleet using th

- **UUID:** `a2ff05d7-b4f9-45e9-8efe-c2149d5d8cba`
- **Slug:** `audit-a-staged-grub-kernel-command-line-rollout-for-a-mixed`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

Audit a staged GRUB/kernel-command-line rollout for a mixed Linux fleet using the task materials in `/app/task_file`. The rollout state is supplied by the harness as records for candidate GRUB files, host boot/runtime state, loaded modules, and policy.

Produce the effective GRUB defaults plus per-host blockers, warnings, aggregate summaries, remediation actions, and deterministic rollout waves from those records only; never inspect the real machine's filesystem, use the network, or install anything at runtime. Follow `/app/task_file/docs/SPEC.md` exactly.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
