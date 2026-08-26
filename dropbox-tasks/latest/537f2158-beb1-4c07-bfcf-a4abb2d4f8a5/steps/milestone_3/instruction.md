With the systemd configuration generated, implement `/app/src/validate.ts` so that running

    npx ts-node /app/src/cli.ts validate

cross-checks the generated unit files against the original operations dossier and the runtime
contracts, then writes `/app/output/validation-report.json`.

The report must confirm:
- Every OS-level access requirement from `/app/output/contracts.json` is reflected in the
  service unit's directives.
- The tmpfiles.d configuration accounts for all directories the coordinator touches at
  runtime.
- The file descriptor count observed in `/app/traces/under-load.lsof` falls within the
  bound documented in `/app/docs/ops-dossier.md`.
- The `LimitNOFILE=` value in the service unit is greater than `contracts.fd_count_observed`.
- Both `StartLimitBurst=5` and `StartLimitIntervalSec=10min` are present in the service
  unit, matching the restart ceiling documented in the incident history.

The required report schema is in `/app/docs/migration-requirements.md`.
