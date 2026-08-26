Using the runtime contracts at `/app/output/contracts.json`, implement
`/app/src/generate.ts` and the writer modules under `/app/src/writers/` so that running

    npx ts-node /app/src/cli.ts generate

produces four files under `/app/output/`:

- `finchrender.service` — a hardened systemd service unit
- `finchrender.socket` — the matching socket activation unit
- `finchrender-tmpfiles.conf` — tmpfiles.d configuration
- `finchrender.env` — environment file

The service unit must apply the security model from `/app/docs/migration-requirements.md`:
capability bounding, privilege restrictions, and device access policies consistent with the
contracts. The socket and tmpfiles entries must match the coordinator's observed runtime
layout.

Beyond the basic structure, the service unit must encode operational decisions derived from
the incident history in `/app/docs/ops-dossier.md`:

- `After=` must include `udev-settle.service` so GPU device enumeration succeeds on hosts
  where the kernel DRM module loads late (see the incident history for context).
- `StartLimitBurst=5` and `StartLimitIntervalSec=10min` must reflect the restart policy
  ceiling documented in the operations dossier incident history.
- `LimitNOFILE=64` must be set to provide a tight file descriptor ceiling above the
  observed maximum while still catching descriptor leaks early.
- `ReadWritePaths=` must include the checkpoint directory from `contracts.checkpoint_dir`
  as well as the cache and log directories.
- `SystemCallFilter=@system-service` covers standard daemon syscalls. A second
  `SystemCallFilter=` line must add the extra syscalls required for the coordinator's
  capability management sequence.

The required output schema is in `/app/docs/migration-requirements.md`.
