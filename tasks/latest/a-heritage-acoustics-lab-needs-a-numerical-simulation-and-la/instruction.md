A heritage acoustics lab needs a numerical simulation and lab calibration closure over CT-derived Baroque violin cavities. Under /app a working finite-difference acoustic assay reconstructs pressure fields, persists cavity mesh staging, recovers spectral formant peaks with reference math, and publishes calibrated reports when closure tolerances hold. This is scientific wave-equation calibration for listening regression, not application service repair or generic CRUD.

Follow the assay workflow in /app/docs/scientific-computing-workflow.md and the calibration closure rules in /app/docs/lab-closure-calibration-contract.md. Supporting contracts: /app/docs/cavity-mesh-staging.md, /app/docs/format_contract.md, /app/docs/calibration_notes.md, /app/docs/lab_notes.md, and /app/docs/assay-operator-commands.md.

Deliverables:

/app/state/<profile>/cavity_mesh.json
/app/output/reports
/app/output/reports/summary.json
/app/output/reports/<profile>/formants.json
/app/output/reports/<profile>/pressure.wav

CT volumes live under /app/data/ct. For each stem, formants.json reports profile, sample_rate_hz, formant_count, formants_hz, peak_prominence_db, pressure_digest, and cavity_speed_digest bound to the mesh staging certificate. Each profile directory also emits mono PCM pressure.wav. summary.json lists sorted profiles and a comma-joined batch_digest. Process every .ctb volume under /app/data/ct. amati_ct is the Amati stem and guarneri_ct is the Guarneri stem. Static JSON written without executing the numerical kernel will not satisfy closure.
