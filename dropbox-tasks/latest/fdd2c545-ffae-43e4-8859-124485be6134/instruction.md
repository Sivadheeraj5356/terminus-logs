# Fleet unit constraint synthesizer

The fleet synthesizer under `/app/environment` turns a declarative manifest plus overlay
files into a verified systemd unit bundle and a deterministic restart trace. The pipeline
currently mis-merges policy layers, mis-maps list fields into unit files, mis-labels slice
entries, and simulates restart ordering incorrectly. Repair the Rust resolver, Go emitters,
Go trace simulator, and tarball packer so the normal rebuild path produces correct outputs.

Run `bash /app/environment/scripts/build.sh` after source edits, then regenerate artifacts
with:

```bash
TB_FLEET_SEED=23 bash /app/environment/scripts/fleet_pipeline.sh
```

Hand-writing `/app/output/fleet_units.tar` or `/app/output/restart_trace.json` is not
sufficient; the verifier deletes outputs and reruns the pipeline.

## Required outputs

- `/app/output/fleet_units.tar` containing `manifest.json` and `units/*` unit bodies.
- `/app/output/restart_trace.json` with restart simulations for every scenario fixture.

Both artifacts use `schema_version` `fleet.unit.v1`. See
`/app/environment/docs/unit_contract.md` and `/app/environment/docs/precedence_matrix.md`
for bundle and precedence rules.

## Precedence contract

Layers rank **cli** above **env** above **manifest** above **default**. Scalars
(`Restart`, `RestartSec`, `Slice`) take the highest-layer value that defines the field.
List fields (`After`, `Requires`, `Wants`) are replaced entirely by the highest layer
that defines them (no union merge).

Graded precedence anchors:

- `acme-worker.service` ends with `Restart=always` and `RestartSec=12`.
- `acme-cache.service` ends with `After=acme-collector.service` and
  `Requires=acme-collector.service` only (no `acme-reporter.service` lines).
- `acme-collector.service` ends with `Slice=fleet.work.slice`.
- `acme-worker.service` keeps distinct `After`, `Requires`, and `Wants` lists.

## Manifest and digests

`manifest.json` entries are sorted by `name` and carry `kind` `slice` for `.slice` units.
Each entry includes a `sha256` digest of the corresponding unit body. `bundle_digest` is
SHA-256 hex over canonical JSON of the sorted entries array.
`trace_digest` is SHA-256 hex over canonical JSON of the `scenarios` array.

## Restart simulation

For each scenario fixture under `/app/environment/data/scenarios/`, the trace lists
`ordered_events` with monotonic `ts_index`. Stops traverse the `Requires` closure of the
trigger in reverse topological order (dependents before dependencies), then stop the
trigger, then start the trigger. The `iota_smoke` scenario touches only
`acme-reporter.service`. `mu_cross_restart` stops `acme-reporter.service` before
`acme-worker.service`. `lambda_requires_order` stops `acme-worker.service` before
`acme-cache.service`.

Every emitted unit must pass offline `systemd-analyze verify` on the unpacked tarball units.
