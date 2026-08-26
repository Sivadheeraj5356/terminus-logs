# Given a 2D acoustic imaging configuration with source and receiver positions aro

- **UUID:** `34a508e9-dd1d-4c53-a01f-fc628212f365`
- **Slug:** `given-a-2d-acoustic-imaging-configuration-with-source-and-re`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Given a 2D acoustic imaging configuration with source and receiver positions around a circular aperture and observed waveform data from multiple source-receiver pairs, implement a ray-based acoustic tomography system that computes straight-ray travel times, models frequency-dependent attenuation, performs iterative velocity reconstruction using travel-time gradient descent, and quantifies reconstruction uncertainty from the diagonal Hessian approximation. The program must read configuration from `/app/config/settings.json`, data from `/app/data/fwi/` (containing `sources.json`, `receivers.json`, and `observed_data.json`), and write the inversion report to `/app/output/fwi_report.json`.

The travel-time for each source-receiver pair is computed as: `travel_time_us = euclidean_distance_in_grid_cells × dx_mm ÷ avg_velocity_mps × 1000` where `avg_velocity_mps` is the arithmetic mean of all cells in the current velocity grid and `euclidean_distance_in_grid_cells = sqrt((sx-rx)² + (sz-rz)²)` using integer grid indices. The initial velocity grid is uniform at `initial_velocity_mps` from settings.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
