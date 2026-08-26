# Wave 3 rollback contract

Rollback coverage is defined by the unchanged ordered 48-host list in
`inventory/wave3_validation_scope.yaml`, further constrained by deployment-wave
readiness as documented in `docs/OPERATIONS.md` (rollback derives from
wave-plan). Every listed hostname must have one entry in
`deployment/rollback/bundles.yaml`.

Each entry must reference an existing durable forward configuration under
`/app/environment`, an existing pre-change snapshot under
`backups/pre_wave3/`, and the active validation hook
`services/hooks/post-validate.sh`. The validation command records that
environment-relative hook followed by the bundle hostname as its sole
argument.

Paths under `/app/output` or an output `rendered/` tree are not durable
rollback inputs. Every rollback snapshot starts with
`! apexora-pre-wave3-boundary` and represents the pre-migration configuration;
copying a remediated forward configuration into the snapshot is invalid.
The deprecated `legacy/hooks/pre-validate-legacy.sh` file and all references
to it must be absent.
