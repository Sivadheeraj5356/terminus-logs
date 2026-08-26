# Fleet unit bundle contract

## Outputs

- `/app/output/fleet_units.tar` contains `manifest.json` and `units/*.service` or `units/*.slice`.
- `/app/output/restart_trace.json` records deterministic restart simulations.

## manifest.json

- `schema_version` is `fleet.unit.v1`.
- `entries` is an array of `{name, kind, sha256}` sorted by `name` ascending.
- `kind` is `service` for `.service` units and `slice` for `.slice` units.
- `bundle_digest` is SHA-256 hex of canonical JSON for the entries array only:
  `json.dumps(entries, sort_keys=True, separators=(",", ":"))`.

## Unit files

Each unit is a systemd snippet with `[Unit]` keys `After=`, `Requires=`, `Wants=`,
`[Service]` keys `Restart=`, `RestartSec=`, and optional `Slice=` on services.

## restart_trace.json

- `schema_version` is `fleet.unit.v1`.
- `scenarios` array matches fixture basenames under `data/scenarios/`.
- Each scenario has `scenario`, `trigger`, `units_touched`, `ordered_events`.
- Each event has `action` (`stop` or `start`), `unit`, `ts_index` (monotonic within scenario).
- Restart stops traverse the Requires closure of `trigger` in reverse topological order
  (dependents before dependencies), then start the trigger.
- `trace_digest` is SHA-256 hex of canonical JSON for the scenarios array only.
