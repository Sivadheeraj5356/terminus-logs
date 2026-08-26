With all four systemd unit files generated, implement `/app/src/audit.ts` so that running

    npx ts-node /app/src/cli.ts audit

reads all strace captures under `/app/traces/`, cross-references the syscall inventory
against systemd's well-known syscall groups, and writes three files to `/app/output/`:

- `syscall-audit.json` — inventory of every syscall name observed across all traces, the
  subset that are not covered by the `@system-service` preset, and the sysctl parameters
  the coordinator requires.
- `99-finchrender-shmmax.conf` — a sysctl.d configuration file enforcing the shared-memory
  ceiling documented in the operations dossier (the value is the minimum `kernel.shmmax`
  established after incident INC-2022-0034).
- `finchrender-drop-in.conf` — a systemd service drop-in that adds `SystemCallFilter` and
  `LimitNOFILE` directives derived from the audit. Drop-in files use the same INI format
  as unit files and must be placed in a `.d/` directory alongside the unit; the format
  requires only a `[Service]` section.

The required output schema is in `/app/docs/migration-requirements.md`.

Key implementation notes:
- Parse ALL `.strace` files in `/app/traces/`, not just the cold-startup trace.
- The `extra_syscalls` field must contain only syscalls NOT covered by `@system-service`.
  The `@system-service` group does NOT include: `capget`, `capset`, `prctl` (these are
  capability management calls that `@system-service` explicitly omits). Do NOT include
  `setuid` or `setgid` — with systemd's `User=` directive those calls become no-ops.
- The sysctl value `67108864` for `kernel.shmmax` is documented in the post-mortem for
  a coordinator crash that occurred when the system shared-memory ceiling was too low.
- The drop-in `finchrender-drop-in.conf` must produce a valid INI file with exactly one
  `[Service]` header followed by the filter and limit lines.
