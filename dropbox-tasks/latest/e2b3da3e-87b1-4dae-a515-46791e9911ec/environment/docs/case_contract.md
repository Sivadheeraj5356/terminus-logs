Case schema version 4.

Required top-level keys in order of documentation: schema_version, case_id, start_time_s, end_time_s, output_interval_s, topology_path, forcing_path, solver.

schema_version must be 4. case_id is a nonempty string. Times are integer seconds with start_time_s <= end_time_s. output_interval_s is a positive integer. topology_path and forcing_path are absolute paths.

solver object keys: initial_step_s, minimum_step_s, maximum_step_s, volume_abs_tolerance_m3, volume_rel_tolerance, newton_abs_tolerance_m3, newton_rel_tolerance, maximum_newton_iterations.

All solver step sizes and the absolute/Newton tolerances (`volume_abs_tolerance_m3`, `newton_abs_tolerance_m3`, `newton_rel_tolerance`) must be finite and strictly positive. `volume_rel_tolerance` must be finite and nonnegative; the value `0.0` is allowed and disables the relative term in the adaptive error scale (absolute-only normalization). maximum_newton_iterations is a positive integer. minimum_step_s <= initial_step_s <= maximum_step_s.

Unknown keys are rejected. Malformed input fails the invocation without mutating outputs.
