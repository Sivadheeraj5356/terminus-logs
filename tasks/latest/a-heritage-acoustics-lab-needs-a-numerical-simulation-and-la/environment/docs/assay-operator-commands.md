# Assay operator commands — CT violin FDTD

Rebuild the numerical kernel and run the calibrated batch:

```
make -C /app/environment
/app/bin/reso_sim batch --ct /app/data/ct --out /app/output/reports
```

Inputs: every `.ctb` under `/app/data/ct` (currently `amati_ct.ctb` and
`guarneri_ct.ctb`). Outputs: per-stem directories under `/app/output/reports/` plus
`summary.json` at the reports root.

The verifier rebuilds and re-runs this assay path before checking closure
tolerances in `/app/docs/lab-closure-calibration-contract.md`.
