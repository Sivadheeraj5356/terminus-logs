# Geometry rollup snapshot

characterize writes /app/state/geometry_rollup.json alongside calibration_tapeout.json. The rollup captures per-geometry aspect weights used during coordinate-descent closure. model-fit must read only the persisted rollup together with the calibration tapeout and parameter bounds.

schema_version is gaa-rollup-v1. Fields include reference_temp_c, measure_digest copied from the sealed calibration tapeout, entries sorted by ascending geometry_id, and rollup_digest sha256 hex. Each entry carries geometry_id, split_group, aspect_weight, iv_weight, and cv_weight.

aspect_weight is round6 of W_nm times nfin divided by L_nm using geometry manifest dimensions in meters-scale nanometer fields. iv_weight is round6 of aspect_weight times the count of IV sweep rows for that geometry_id in the tapeout. cv_weight is round6 of aspect_weight times the count of CV sweep rows for that geometry_id in the tapeout.

rollup_digest is sha256 hex over newline-joined lines sorted by geometry_id. Each line is entry pipe geometry_id pipe split_group pipe big-endian IEEE754 hex of aspect_weight pipe hex of iv_weight pipe hex of cv_weight. Float hex encoding matches /app/scripts/digest_contract.py and /app/docs/tapeout-schema.md.

Coordinate-descent combined RMSE for a split group uses weighted root mean square error. For Id residuals sum iv_weight times squared error over IV points in the group divided by the sum of iv_weight for those points, then take the square root. For Cgg residuals use cv_weight the same way. Combined RMSE is the square root of the sum of squared weighted Id RMSE and squared weighted Cgg RMSE. group_metrics id_rmse and cv_rmse in model_validation.json use the same weighted formulas rounded to six decimal places.

The rollup file is written atomically using the same temp rename pattern as calibration_tapeout.json. model-fit rejects when the rollup file is missing, when measure_digest does not match the tapeout, or when rollup_digest does not recompute from entries.
