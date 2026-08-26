# Checkpoints and digest seals

## CLI

```bash
/app/bin/hann_energy_audit --pack <pack.json> --out <report.json> [--checkpoint <state.json>]
```

`--pack` and `--out` are required. `--checkpoint` is optional and is valid only for schema-version 3 packs. Providing `--checkpoint` with a schema-version 2 pack is an error.

Create missing parent directories for `--out` and `--checkpoint` before writing.

## Atomic writes

Report and checkpoint updates must be atomic temp-then-rename writes into the final paths. On malformed packs, stale checkpoints, fingerprint mismatch, I/O errors, or any other failure:

- leave any pre-existing `--out` report bytes unchanged
- leave any pre-existing `--checkpoint` bytes unchanged
- exit non-zero with a stderr message

Successful runs replace the report (and checkpoint when requested) only after the full evaluation finishes.

## Pack fingerprint

Schema-version 3 pack fingerprint is lowercase SHA-256 over the UTF-8 seal:

```
schema_version|scenario_seal|scenario_seal|...
```

Each scenario seal is:

```
id|timeline_len|sample_rate_hz|frame_len|hop_len|detrend|gap_policy|min_frame_quality|band_name:low_hz:high_hz:weight|...|sample_revision_ids|calibration_revision_ids|timeline_csv
```

Formatting rules:

- Floats in the fingerprint use exactly 12 decimal places.
- `sample_revision_ids` is the comma-joined ordered list of sample `revision_id` values (empty string when there are no sample revisions).
- `calibration_revision_ids` is analogous for calibration revisions.
- `timeline_csv` is the calibrated dense timeline with `null` for missing samples and `%.12f` for numeric samples, comma-joined.

## Checkpoint file

Checkpoint JSON schema:

```json
{
  "schema_version": 3,
  "pack_fingerprint": "lowercase sha256 hex",
  "completed": [
    {"id": "scenario-id", "digest_hex": "lowercase sha256 hex"}
  ]
}
```

`completed` preserves scenario completion order.

## Resume rules

When `--checkpoint` is omitted, evaluate every scenario and write only the report.

When `--checkpoint` is provided:

1. If the checkpoint path does not exist, evaluate every scenario, then write the report and a fresh checkpoint covering all scenarios.
2. If the checkpoint exists but is malformed, refuse to run and leave outputs unchanged.
3. If `pack_fingerprint` does not match the current pack, refuse to run and leave outputs unchanged.
4. If the fingerprint matches, treat scenarios whose `id` appears in `completed` as already done. Reconstruct the report prefix from those stored digests only when every completed prefix scenario is present in the current pack in the same order with identical digests after re-evaluation of any non-completed suffix. Practically: re-evaluate all scenarios; for ids listed in `completed`, the recomputed `digest_hex` must equal the stored digest or the run fails without writing; scenarios not listed are newly computed. The final report always contains every scenario from the pack in pack order.
5. After a fully successful run, rewrite the checkpoint so `completed` lists every scenario id with its final digest and the current pack fingerprint.

Resuming never skips spectral evaluation for correctness checking of stored digests: stored digests are validated against a fresh evaluation. The checkpoint exists to detect stale or mismatched partial work, not to short-circuit numeric recomputation in this tool.

## Scenario digest seals

Float formatting in all seals uses fixed decimals with exactly 12 places. Digests are lowercase SHA-256 hex.

### Schema-version 2 scenario seal

```
id|sample_count|valid_sample_count|frame_len|hop_len|frame_count|dropped_frame_count|window_energy|band_name:low_hz:high_hz:bin_count:peak_bin:peak_hz:energy|...
```

### Schema-version 3 scenario seal

First compute `lineage_hex` as SHA-256 of:

```
sample_revision_ids|calibration_revision_ids|timeline_csv
```

using the same revision-id joining and timeline CSV rules as the pack fingerprint.

Then the scenario seal is:

```
id|sample_count|valid_sample_count|frame_len|hop_len|frame_count|dropped_frame_count|rejected_frame_count|window_energy|lineage_hex|band_name:low_hz:high_hz:weight:bin_count:peak_bin:peak_hz:energy|...
```

Band segments follow input band order.

## Summary digest seals

### Schema-version 2

```
schema_version|scenario_count|band_result_count|total_frame_count|total_dropped_frames|scenario_digest|...
```

### Schema-version 3

```
schema_version|scenario_count|band_result_count|total_frame_count|total_dropped_frames|total_rejected_frames|scenario_digest|...
```

Scenario digests are appended in report order.
