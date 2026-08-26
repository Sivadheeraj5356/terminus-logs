# Channel selection

Each migrate host under `/app/config/migrate-hosts.json` declares importer
bindings keyed by catalog alias. Selection for an alias:

1. Load candidates from `/app/config/catalog.json` pins for that alias.
2. Keep only candidates whose train window contains the active train epoch:
   `minTrainEpoch <= epoch` and (`maxTrainEpoch` is null/absent or `epoch <= maxTrainEpoch`).
3. Also require the candidate `channel` to be listed on the active train's
   `channels` array.
4. Among remaining candidates, prefer the importer `channelHint` when that
   channel is still present. Otherwise prefer the pin `defaultChannel` when
   present. Otherwise take the lexicographically smallest package name.
5. Emit importer edges as `workspace:<package>@*`.

Different importers may select different packages for the same alias when
their channel hints differ.

App `package.json` files expose matching `dependencies` maps, and
`/app/pnpm-lock.yaml` importer edges use matching `specifier` values with
`version: link:...` targets that resolve to the selected package paths.

`/app/reports/build-summary.json` reports providers `consoleRuntime`,
`consoleAdapter`, `workerRuntime`, and `workerPlugin` (package names for the
console/worker runtime, adapter, and plugin aliases) plus the closed `peers`
list and plan `fingerprint`.

`/app/reports/seal-audit.json` includes an `errors` array that must be empty
on a successful seal.

Under the checked-in hosts and catalog, with open tip `train-east` at epoch
`5`, sealed direct targets are `runtime-canary` and `adapter-next` for
`apps/console`, and `runtime-stable` and `plugin-extra` for `apps/worker`.
Those provider names appear in `/app/reports/build-summary.json`. When the
open tip falls to `train-west` at epoch `4`, console runtime becomes
`runtime-stable`, console adapter becomes `adapter-legacy`, and worker plugin
becomes `plugin-core`.
