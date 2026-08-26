# Measurement source overlays

Lab calibration may substitute alternate measurement directories and bound sets without changing the compact-model equations. Absolute overlay roots are required so closure experiments remain deterministic.

TB3_GAA_DATA_ROOT replaces the bundled measurement directory for characterize. The overlay directory must be absolute and must contain iv_sweep.csv, cv_sweep.csv, geometry_manifest.json, and contact_resistance.json.

TB3_GAA_BOUNDS_ROOT replaces the bounds file selection for model-fit. The overlay must be absolute and must contain parameter_bounds.toml. While that variable is set and non-empty, resolve bounds exclusively as the join of the overlay directory and parameter_bounds.toml. The --bounds CLI path may still appear on the command line, but model-fit must not open or apply that path while the overlay is active.

Overlay precedence is absolute. When TB3_GAA_BOUNDS_ROOT is set and non-empty, model-fit never opens the --bounds path and reads the solver limits, the per-parameter min max initial triples, and every shared_group tie_break_order only from the overlay parameter_bounds.toml. All split groups are refit against those overlay bounds. Because the overlay may change bounds and tie_break_order, the fitted parameter values, the group_metrics, and the validation_digest differ from a fit that used the default --bounds file.

Overlays apply independently. Setting only TB3_GAA_DATA_ROOT leaves default bounds unless TB3_GAA_BOUNDS_ROOT is also set. Empty overlay variables fall back to documented defaults. Relative overlay paths are rejected with non-zero exit for both TB3_GAA_DATA_ROOT and TB3_GAA_BOUNDS_ROOT.

