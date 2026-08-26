# Operator Runbook

## `/app/bin/specz-worker --once`

Process all `*.spz` frames in `/data/inbox` and recover stale `.processing` claims from `/data/work`. Valid scans are committed to `/data/state` and materialized to `/output/drift.jsonl` sorted by `instrument`, `session`, `sequence`. Corrupt or conflicting inputs move to `/data/quarantine`. Emits JSON Lines lifecycle events on stdout: a leading `{"type":"worker/start",...}`, per-file `processed` / `skipped` / `quarantined` events, and a final `{"type":"worker/stop","processed":N,"skipped":N,"quarantined":N}`. Exit code `0` when the batch completes, even if some files were quarantined.

## Scan record schema (`/output/drift.jsonl`)

Each line is one scan object with: `type` (`scan`), `instrument`, `session`, `sequence` (integer), `source_sha256` (lowercase hex digest of original frame bytes), `calibration_revision` (string), `sample_count` (integer), `peak_centroid_nm`, `drift_pm`, `integrated_intensity`, `baseline_noise` (finite numbers per notebook definitions).

## `/app/bin/specz-worker inspect <frame>`

Print one JSON object: `version`, `instrument`, `session`, `sequence`, `sample_count`, `calibration_revision`, `masked_pixels`, `crc_ok`. No spool, archive, quarantine, state, or output side effects.

## Configuration precedence

Path and analysis overrides: environment variables (`SPECZ_INBOX`, `SPECZ_WORK`, `SPECZ_REFERENCE_NM`, and other `SPECZ_*` keys) > `/app/config/site.conf` > `/app/config/defaults.conf`. Site config must not override the calibration revision embedded in each frame.

Verifier campaign frame labels used in regression replay include `delta-reverse.spz`, `config-frame.spz`, `reserved-flags.spz`, stale work suffix `committed.processing`, and claim file `stale-claim.processing`.

## Tools

| Script | Purpose |
|---|---|
| `dump-frame-bytes.sh` | Hex/decimal byte dump via `od` |
| `replay-visible-spool.sh` | Reset demo spool and run worker |
| `reset-visible-spool.sh` | Restore pristine visible `/data` layout |
| `validate-jsonl.sh` | Validate JSON Lines syntax |

## Maintainer checksum tooling

Creator regeneration may write `pristine_checksums.json` beside verifier tests using a `--write-checksums` flag on the fixture generator CLI.

| Path | Role |
|---|---|
| `/data/inbox` | Incoming frames |
| `/data/work` | Claimed `.processing` files |
| `/data/archive` | Handled source frames |
| `/data/quarantine` | Rejected inputs |
| `/data/state/manifest.tsv` | Committed scan index |
| `/data/state/results/` | Per-scan JSON fragments |
| `/output/drift.jsonl` | Sorted scan output |
