# Given a 2D acoustic imaging configuration with source and receiver positions aro

Submission: `34a508e9-dd1d-4c53-a01f-fc628212f365`  
Slug: `given-a-2d-acoustic-imaging-configuration-with-source-and-re`  
Latest archive: `34a508e9-dd1d-4c53-a01f-fc628212f365_submission_2026-07-19T20_25_19.884Z.zip`  
Revisions: 1

## Task summary

Given a 2D acoustic imaging configuration with source and receiver positions around a circular aperture and observed waveform data from multiple source-receiver pairs, implement a ray-based acoustic tomography system that computes straight-ray travel times, models frequency-dependent attenuation, performs iterative velocity reconstruction using travel-time gradient descent, and quantifies reconstruction uncertainty from the diagonal Hessian approximation. The program must read configuration from `/app/config/settings.json`, data from `/app/data/fwi/` (containing `sources.json`, `receivers.json`, and `observed_data.json`), and write the inversion report to `/app/output/fwi_report.json`. The travel-time for each source-receiver pair is computed as: `travel_time_us = euclidean_distance_in_grid_cells × dx_mm ÷ avg_velocity_mps × 1000` where `avg_velocity_mps` is the arithmetic mean of all cells in the current velocity grid and `euclidean_distance_in_grid_cells = sqrt((sx-rx)² + (sz-rz)²)` using integer grid indices. The initial velocity grid is uniform at `initial_velocity_mps` from settings. All reconstructed velocity values must lie in the range [1000, 2000] m/s. The `frequencies_used` array in the output must be sorted in ascending order.

Required artifacts include: `/app/config/settings.json`, `/app/data/fwi/`, `/app/output/fwi_report.json`.

Author anonymous tagged this **hard** scientific-computing task (full-waveform-inversion, acoustic-wave-equation, medical-imaging).

Time estimates: expert ~90.0 min, junior ~180.0 min.

Harbor timeouts: agent 1200s, verifier 450s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `34a508e9-dd1d-4c53-a01f-fc628212f365_submission_2026-07-19T20_25_19.884Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
