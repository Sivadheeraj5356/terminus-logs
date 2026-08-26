# Lab calibration kernel entry points

The characterization kernel under /app implements the numerical device-calibration and compact-model closure in /app/docs/device-characterization-contract.md and /app/docs/compact-model.md. Sources in /app/tb3 supply the Rust calibration kernel and must compile before the lab binary is usable. Lab calibration runs through the gaa-extract entry point at /app/bin/gaa-extract after a release rebuild from /app sources via /app/scripts/build.sh (cargo and rustc are on PATH under /usr/local/cargo/bin). Calibration stages are characterize, model-fit, and run. The published SPICE card must follow /app/docs/spice-card.md exactly, including asterisk-space header spacing and .param lines with no spaces around equals. When TB3_GAA_BOUNDS_ROOT is set and non-empty, model-fit loads only that overlay parameter_bounds.toml and ignores --bounds for that invocation.

characterize flags: --data-dir absolute bundled root default /app/data/bundled, --tapeout default /app/state/calibration_tapeout.json, --rollup default /app/state/geometry_rollup.json. This step builds the calibration snapshot and geometry rollup artifact used by the numerical fit per /app/docs/geometry-rollup.md. Relative --data-dir values are rejected with non-zero exit.

model-fit flags: --tapeout, --rollup default /app/state/geometry_rollup.json, --bounds default /app/config/parameter_bounds.toml, --spice default /app/out/gaa_model.sp, --validation default /app/out/model_validation.json. model-fit applies the compact-model equations and coordinate-descent closure reading only the persisted calibration snapshot, geometry rollup, and bounds.

run executes characterize then model-fit with the same paths. The model-fit stage of run must still read only the persisted calibration_tapeout.json and parameter bounds, without reopening bundled CSV or JSON measurement inputs. Default tapeout and output parents /app/state and /app/out exist in the workspace image.

Overlay environment variables TB3_GAA_DATA_ROOT and TB3_GAA_BOUNDS_ROOT must be absolute paths. When TB3_GAA_DATA_ROOT is set and non-empty, characterize reads iv_sweep.csv, cv_sweep.csv, geometry_manifest.json, and contact_resistance.json from that overlay root instead of --data-dir. When TB3_GAA_BOUNDS_ROOT is set and non-empty, model-fit loads parameter_bounds.toml from that overlay root instead of the --bounds path; the --bounds flag remains present on the command line but must not be used while the overlay is active. Relative overlay values are rejected with non-zero exit. Empty overlay variables fall back to the documented defaults. See /app/docs/measurement-source-overlays.md.



