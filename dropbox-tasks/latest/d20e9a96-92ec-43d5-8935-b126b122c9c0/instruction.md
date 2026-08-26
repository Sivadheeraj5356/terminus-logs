The backup utility under `/app` manages five labs. A maintenance window left the system unable to complete its `fieldday-2026-06-18` restore drill — the tool exits with errors and produces no output.

The operational state of the data layer was disrupted by the maintenance. Documentation under `/app/docs/` describes the storage layout and output contracts. The tool source is under `/app/src/`.

Reconcile the system state so that the restore drill writes byte-correct files under `/app/restore/fieldday-2026-06-18/` and a valid provenance report at `/app/repair.json` per the contract in `/app/docs/repair-contract.md`. The neighboring snapshot `steady-2026-06-17` must also restore correctly through the same tool.

Immutable artifacts: object pool byte data, recipe definitions, and compiled tool sources.
