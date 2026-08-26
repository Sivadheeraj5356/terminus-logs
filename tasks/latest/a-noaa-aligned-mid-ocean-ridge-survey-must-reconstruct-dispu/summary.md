# A NOAA-aligned mid-ocean ridge survey must reconstruct disputed ROV dive lanes a

- **UUID:** `f4d8b626-6922-4b17-b1c3-2e21510bff99`
- **Slug:** `a-noaa-aligned-mid-ocean-ridge-survey-must-reconstruct-dispu`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

A NOAA-aligned mid-ocean ridge survey must reconstruct disputed ROV dive lanes after calibration drift across the Clarion-Clipperton fracture zone. Sonar observers filed competing depth reports across north trench and south ridge lanes, hydrothermal vent anchors, and superseded calibration sweeps.

The expedition control cell needs a reproducible chain that normalizes Ocean Expedition Log bundle provenance, arbitrates lane precedence under published dive policy, links survivor observations into a feature timeline, binds replay counters to staging witnesses, and exports a sealed expedition atlas for peer review. The expeditctl tool under /app integrates ingest-dive-log, resolve-precedence, reconcile-observations, and export-atlas.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
