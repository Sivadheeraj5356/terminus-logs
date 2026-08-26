# Lab closure calibration contract — CT violin formants

Closure means every shipped CT stem yields four accepted formant frequencies
within `formant_tolerance_hz` of the lab regression targets produced by the
documented FDTD protocol, and the strongest accepted peak meets `peak_min_db`.

## Numeric reference

- Frequency tolerance: five hertz (`formant_tolerance_hz` in `lab.toml`).
- Prominence floor: six decibels absolute spectral magnitude (`peak_min_db`),
  not relative or median prominence.
- Cross-profile ordering: lowest amati peak below the third guarneri peak.
- Drive, Courant factor squared, bridge and mic cells, and peak separation are
  specified in `/app/docs/calibration_notes.md`.

## Closure artifacts

| Path | Role |
| --- | --- |
| `/app/state/<profile>/cavity_mesh.json` | Mesh staging certificate before leapfrog |
| `/app/output/reports/<profile>/formants.json` | Spectral closure certificate per stem |
| `/app/output/reports/<profile>/pressure.wav` | Microphone pressure time series |
| `/app/output/reports/summary.json` | Batch inventory of closed stems |

A report that only matches schema without landing inside the frequency and
prominence tolerances does not constitute closure.
