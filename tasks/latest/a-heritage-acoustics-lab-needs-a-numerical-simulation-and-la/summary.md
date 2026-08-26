# A heritage acoustics lab needs a numerical simulation and lab calibration closur

- **UUID:** `861f1699-1ec6-40df-8f1a-a1ec60b5e77e`
- **Slug:** `a-heritage-acoustics-lab-needs-a-numerical-simulation-and-la`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

A heritage acoustics lab needs a numerical simulation and lab calibration closure over CT-derived Baroque violin cavities. Under /app a working finite-difference acoustic assay reconstructs pressure fields, persists cavity mesh staging, recovers spectral formant peaks with reference math, and publishes calibrated reports when closure tolerances hold.

This is scientific wave-equation calibration for listening regression, not application service repair or generic CRUD. Follow the assay workflow in /app/docs/scientific-computing-workflow.md and the calibration closure rules in /app/docs/lab-closure-calibration-contract.md.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
