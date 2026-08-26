# Planetary thermophysics for a synthetic Diviner-style lunar regolith column: rec

- **UUID:** `faa9b80b-4c7a-45fe-94df-64b67f1698e9`
- **Slug:** `planetary-thermophysics-for-a-synthetic-diviner-style-lunar`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Planetary thermophysics for a synthetic Diviner-style lunar regolith column: recover subsurface temperatures, surface energy balance, multi-band brightness temperatures, and bounded thermal-inertia parameter fits from the frozen offline inputs under `/app/data` (materials, nonuniform depth grid, diurnal/eclipse/gradient illumination, forcing intervals, eclipse transmission, radiometer bands, observation queries, and inversion queries). Normative physics, units, tolerances, and the JSON shape live in `/app/docs` — especially `thermal_model_contract.md`, `radiometer_contract.md`, `inversion_contract.md`, `data_contract.md`, `report_contract.md`, `report_schema.json`, and `failure_contract.md`.

A successful run must write `/app/output/report.json` covering every accepted time step and observation: layer temperatures, surface fluxes, band radiances and brightness temperatures, one- and two-parameter inverse fits (conductivity scale / albedo offset) against the brightness-temperature targets, plus the diagnostics those docs require. Floats must be finite; stay fully offline from the shipped snapshot.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
