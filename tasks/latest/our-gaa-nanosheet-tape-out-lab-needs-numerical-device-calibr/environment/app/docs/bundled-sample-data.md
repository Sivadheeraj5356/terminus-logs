# Bundled sample data

Bundled lab fixtures support the scientific-computing calibration closure described in /app/docs/device-characterization-contract.md. Default measurements sit under /app/data/bundled with three geometries G1 G2 in split_group A and G3 in split_group B. Reference temperature is 25.0 degrees Celsius.

The four default measurement inputs read by characterize are /app/data/bundled/iv_sweep.csv, /app/data/bundled/cv_sweep.csv, /app/data/bundled/geometry_manifest.json, and /app/data/bundled/contact_resistance.json. Parameter bounds for the fit are read from /app/config/parameter_bounds.toml. Published calibration artifacts are the sealed snapshot /app/state/calibration_tapeout.json and the signoff outputs /app/out/gaa_model.sp and /app/out/model_validation.json.

contact_resistance.json maps geometry_id to ohmic contact value used in Id self-consistency. IV sweeps span subthreshold and linear regions. CV sweeps cover depletion and accumulation sides.

These fixtures exercise shared-group fitting, contact drop, and independent group B compact-model closure without external PDK files.

