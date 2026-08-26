The FinchRender render-farm coordinator is being migrated to systemd. Under `/app/docs/` you
will find an operations dossier, a migration requirements spec, and an architecture overview.
Under `/app/traces/` are strace and lsof captures from the coordinator's startup and
steady-state operation. Under `/app/legacy/` are the original YAML and TOML configuration
files.

Implement `/app/src/extract.ts` (and any helpers you need under `/app/src/`) so that running

    npx ts-node /app/src/cli.ts extract

produces `/app/output/contracts.json`. The file must capture the coordinator's runtime
identity (user, group), the UNIX socket it binds, the Linux capabilities it retains after
privilege drop, the environment variables injected at startup, the directories it opens for
cache operations, the checkpoint directory for job state persistence, the OS-level access
requirements documented in `/app/docs/ops-dossier.md`, and the full deduplicated syscall
inventory across all strace captures in `/app/traces/`.

The required JSON schema is in `/app/docs/migration-requirements.md`.

Key extraction rules:
- **capabilities**: use only the FINAL `capset` call's `effective` set; ignore pre-drop
  `capget` results which show the full root capability set.
- **checkpoint_dir**: read from `checkpoints.dir` in `/app/legacy/coordinator.yaml`.
- **syscall_set**: parse ALL `.strace` files under `/app/traces/` (not just
  `startup-cold.strace`), deduplicate, and sort alphabetically.
- **env_vars**: include only `FINCHRENDER_*` variables from the `execve` envp argument.
