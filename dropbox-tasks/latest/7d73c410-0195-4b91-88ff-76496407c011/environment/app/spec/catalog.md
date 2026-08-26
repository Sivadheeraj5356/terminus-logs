# Instrument And Calibration Metadata

`/app/catalog.sqlite` contains the numerical constants for the spectral inverse
problem.

## instruments

| Column | Meaning |
|---|---|
| instrument_id | Numeric id used by observation bundles |
| code | Short station code |
| sample_rate_hz | Nominal sampling rate |
| clock_ppm | Clock correction in parts per million |
| phase_offset_rad | Constant phase offset for this instrument |
| noise_floor | Approximate RMS noise level |

Corrected time for a raw time `t` is `t / (1 + clock_ppm * 1e-6)`.

## calibration_lines

| Column | Meaning |
|---|---|
| label | Calibration source label |
| f0_hz | Frequency at survey epoch |
| chirp_hz_per_s | Linear drift rate |
| start_s | Beginning of activity |
| end_s | End of activity |

Calibration lines are reference tones, not unknown physical sources.

## survey_windows

| Column | Meaning |
|---|---|
| window_id | Window id shared across instruments |
| start_s | Approximate survey start time |
| end_s | Approximate survey end time |
| weight | Relative confidence weight |
