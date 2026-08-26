# Planetary thermophysics for a synthetic Diviner-style lunar regolith column: rec

Submission: `faa9b80b-4c7a-45fe-94df-64b67f1698e9`  
Slug: `planetary-thermophysics-for-a-synthetic-diviner-style-lunar`  
Latest archive: `faa9b80b-4c7a-45fe-94df-64b67f1698e9_submission_2026-07-20T21_25_56.092Z.zip`  
Revisions: 2

## Task summary

Planetary thermophysics for a synthetic Diviner-style lunar regolith column: recover subsurface temperatures, surface energy balance, multi-band brightness temperatures, and bounded thermal-inertia parameter fits from the frozen offline inputs under `/app/data` (materials, nonuniform depth grid, diurnal/eclipse/gradient illumination, forcing intervals, eclipse transmission, radiometer bands, observation queries, and inversion queries). Normative physics, units, tolerances, and the JSON shape live in `/app/docs` — especially `thermal_model_contract.md`, `radiometer_contract.md`, `inversion_contract.md`, `data_contract.md`, `report_contract.md`, `report_schema.json`, and `failure_contract.md`. A successful run must write `/app/output/report.json` covering every accepted time step and observation: layer temperatures, surface fluxes, band radiances and brightness temperatures, one- and two-parameter inverse fits (conductivity scale / albedo offset) against the brightness-temperature targets, plus the diagnostics those docs require. Floats must be finite; stay fully offline from the shipped snapshot. The data directory and report path may be overridden (`lunar-regolith-solver --data-dir PATH --output PATH`; defaults `/app/data` and `/app/output/report.json`).

Required artifacts include: `/app/data`, `/app/docs`, `/app/output/report.json`.

Author anonymous tagged this **hard** scientific-computing task (planetary-science, lunar-regolith, thermophysics, heat-transfer, radiometry, thermal-inertia).

Time estimates: expert ~90 min, junior ~210 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `faa9b80b-4c7a-45fe-94df-64b67f1698e9_submission_2026-07-20T21_25_56.092Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
