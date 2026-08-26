# Hann bin energy audit contract

## Purpose

The `hann_energy_audit` CLI reads a scenario pack, applies overlapping Hann-windowed frames with optional mean detrending, evaluates discrete-frequency bins with the Goertzel algorithm per band, and writes a deterministic spectral audit report. Schema-version 2 packs use a flat sample array. Schema-version 3 packs use revisioned sparse timelines, calibration, frame-quality rejection, weighted bands, and optional checkpointed runs. Detailed rules live in:

- `/app/docs/pack-v3.md`
- `/app/docs/spectral-processing.md`
- `/app/docs/checkpoint-and-seals.md`

## Commands

Rebuild and install after source changes:

```bash
cmake -S /app/environment -B /app/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/app
cmake --build /app/build -j2
cmake --install /app/build
```

Run:

```bash
/app/bin/hann_energy_audit --pack /app/inputs/pack.json --out /app/output/report.json
```

Schema-version 3 optional checkpoint:

```bash
/app/bin/hann_energy_audit --pack <pack.json> --out <report.json> --checkpoint <state.json>
```

## Schema-version 2 input pack

Top-level integer `schema_version` must be **2**. Array `scenarios` where each object contains:

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Scenario label echoed in output |
| `sample_rate_hz` | number | Sampling rate in hertz (finite) |
| `frame_len` | integer | Hann frame length `N` (positive) |
| `hop_len` | integer | Frame hop in samples (positive) |
| `detrend` | string | `"none"` or `"mean"` |
| `gap_policy` | string | `"zero_fill"` or `"skip_frame"` |
| `bands` | object[] | Frequency bands to evaluate |
| `samples` | number\|null[] | Equally spaced amplitudes, oldest first |

Each band object contains:

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Band label echoed in output |
| `low_hz` | number | Inclusive lower band edge (finite) |
| `high_hz` | number | Exclusive upper band edge (finite) |

Example:

```json
{
  "schema_version": 2,
  "scenarios": [
    {
      "id": "scenario-id",
      "sample_rate_hz": 320.0,
      "frame_len": 32,
      "hop_len": 16,
      "detrend": "none",
      "gap_policy": "zero_fill",
      "bands": [
        {"name": "low", "low_hz": 40.0, "high_hz": 80.0}
      ],
      "samples": [0.0, 1.0, null, -0.5]
    }
  ]
}
```

Malformed required fields must produce a non-zero exit code and a helpful error message on stderr without modifying existing outputs.

## Schema-version 3 packs

See `/app/docs/pack-v3.md`. Processing after reconstruction follows `/app/docs/spectral-processing.md`. Checkpoint and sealing rules follow `/app/docs/checkpoint-and-seals.md`.

## Frame, window, Goertzel, and peak rules

Shared spectral rules for both schema versions are defined in `/app/docs/spectral-processing.md`. Schema-version 2 uses implicit band weight `1.0` and does not reject frames for quality.

## Schema-version 2 output report

Write JSON to the `--out` path. Create missing parent directories for the output path.

```json
{
  "schema_version": 2,
  "scenarios": [
    {
      "id": "scenario-id",
      "sample_count": 128,
      "valid_sample_count": 126,
      "frame_len": 32,
      "hop_len": 16,
      "frame_count": 7,
      "dropped_frame_count": 0,
      "window_energy": 11.625,
      "bands": [
        {
          "name": "low",
          "low_hz": 40.0,
          "high_hz": 80.0,
          "bin_count": 4,
          "peak_bin": 5,
          "peak_hz": 50.0,
          "energy": 0.00123456789
        }
      ],
      "digest_hex": "lowercase sha256 hex"
    }
  ],
  "summary": {
    "scenario_count": 1,
    "band_result_count": 1,
    "total_frame_count": 7,
    "total_dropped_frames": 0,
    "digest_hex": "lowercase sha256 hex"
  }
}
```

Preserve scenario order from the input pack. Preserve band order within each scenario. Do not sort output rows.

## Schema-version 3 output report

```json
{
  "schema_version": 3,
  "scenarios": [
    {
      "id": "scenario-id",
      "sample_count": 96,
      "valid_sample_count": 90,
      "frame_len": 32,
      "hop_len": 16,
      "frame_count": 4,
      "dropped_frame_count": 1,
      "rejected_frame_count": 2,
      "window_energy": 11.625,
      "lineage_hex": "lowercase sha256 hex",
      "bands": [
        {
          "name": "low",
          "low_hz": 40.0,
          "high_hz": 80.0,
          "weight": 1.25,
          "bin_count": 4,
          "peak_bin": 5,
          "peak_hz": 50.0,
          "energy": 0.00123456789
        }
      ],
      "digest_hex": "lowercase sha256 hex"
    }
  ],
  "summary": {
    "scenario_count": 1,
    "band_result_count": 1,
    "total_frame_count": 4,
    "total_dropped_frames": 1,
    "total_rejected_frames": 2,
    "digest_hex": "lowercase sha256 hex"
  }
}
```

## Digest sealing

Digest construction for both schema versions is specified in `/app/docs/checkpoint-and-seals.md`.

## CLI rules

The binary accepts `--pack <path>` and `--out <path>`, optionally `--checkpoint <path>` for schema-version 3, writes JSON to the requested output path using atomic updates, creates missing parent directories, returns non-zero for missing arguments or malformed packs, and must not depend on `/app/inputs/pack.json`.

## Numeric tolerances

Apply absolute tolerance `1e-9` with `rel=0` to `window_energy`, `low_hz`, `high_hz`, `peak_hz`, `weight`, and `energy`. Digest and lineage fields use exact equality. After source changes, rebuild and install the CLI from the C++ modules under `/app/environment` via CMake, then regenerate audit reports with `hann_energy_audit` for the scenario packs being processed. Static or manual output writes are insufficient.
