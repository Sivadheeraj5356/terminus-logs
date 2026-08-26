# Validation JSON schema

model_validation.json uses schema_version model-validation-v1. Fields include reference_temp_c, rollup_digest copied from geometry_rollup.json, fitted_groups array with split_group and values map, group_metrics with id_rmse and cv_rmse per split_group, convergence with iterations and final_rmse, and validation_digest sha256 hex. The fitted_groups and group_metrics arrays are ordered by ascending lexicographic split_group name. The validation document carries fitted closure metrics only; measure_digest belongs on calibration_tapeout.json per /app/docs/tapeout-schema.md. Signoff consumers expect this field set and reject other top-level keys.

group_metrics id_rmse and cv_rmse are root mean square error in amperes for Id and farads for Cgg, each rounded to six decimal places with half-up rounding before write.

convergence.iterations is the maximum outer coordinate-descent iteration count across fitted split groups and is always at least one after a successful model-fit. convergence.final_rmse is the maximum final combined RMSE across those groups, rounded to six decimal places.

validation_digest is sha256 hex over newline-joined lines in this order. For each fitted group emit group pipe split_group, then one line per parameter name in ascending sort order as name pipe big-endian IEEE754 hex of the fitted value. For each group_metrics row emit metric pipe split_group pipe id_rmse hex pipe cv_rmse hex using the same hex encoding. Then iter pipe iteration count as decimal digits, then rmse pipe final_rmse hex. The digest field itself is not hashed.

Cross-language float hex and rounding helpers live in /app/scripts/digest_contract.py and match measure_digest encoding in /app/docs/tapeout-schema.md.

