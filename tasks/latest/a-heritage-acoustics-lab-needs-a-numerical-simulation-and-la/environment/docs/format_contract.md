# CT volume binary (.ctb)

Little-endian header: uint32 nx, uint32 ny, then nx * ny voxel bytes (`0` air cavity,
`1` wood shell). Grid constants live in `include/ac_limits.h`.

The numerical assay consumes every `.ctb` in `/app/data/ct` (currently
`amati_ct.ctb` and `guarneri_ct.ctb`) and emits one report subdirectory per
basename. Operator commands are in `/app/docs/assay-operator-commands.md`.

## Per-profile outputs

`/app/output/reports/<profile>/formants.json` fields:

- profile — CT basename
- sample_rate_hz — 83333
- formant_count — four accepted peaks
- formants_hz — four peak frequencies in hertz
- peak_prominence_db — decibel magnitude of the strongest accepted peak
- pressure_digest — 64-character lowercase hex over comma-joined pressure samples
- cavity_speed_digest — must equal staging `speed_digest` for the same profile

`/app/output/reports/<profile>/pressure.wav` — mono 16-bit little-endian PCM, standard
44-byte RIFF header, at least 200 bytes of sample payload (bits-per-sample field 16).

## Summary

`/app/output/reports/summary.json` lists sorted profiles and comma-joined batch_digest.

## Acceptance

Formant peak frequencies must match the lab regression targets for each CT stem within
five hertz (`formant_tolerance_hz` in `lab.toml`). Those targets are defined by the
drive, Courant, and absolute-dB peak protocol in `/app/docs/calibration_notes.md` on the
shipped volumes — not by an alternate analytical cavity model. Closure rules are restated
in `/app/docs/lab-closure-calibration-contract.md`. The strongest accepted peak must meet
a six decibel prominence floor (`peak_min_db`). Cross-profile ordering expects the lowest
amati peak below the third guarneri peak when both profiles are processed.
