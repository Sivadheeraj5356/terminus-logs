# Parameter bounds policy

parameter_bounds.toml declares schema_version gaa-bounds-v1, a reference block with temp_c and vt, solver limits, per-parameter min max initial triples, and shared_groups with tie_break_order lists.

The combined RMSE for a split_group is the square root of the sum of squares of two unrounded component errors. The Id component is the square root of the mean over that group's IV points of the squared difference between measured id_amps and predicted Id. The Cgg component is the square root of the mean over that group's CV points of the squared difference between measured cgg_f and predicted Cgg. Predicted Id and Cgg use round12 per /app/docs/compact-model.md, but the two component RMSEs and their quadrature sum are not rounded when driving the optimizer. The six-place id_rmse and cv_rmse in /app/docs/validation-schema.md are report-only metrics and are not the optimization objective.

Coordinate descent walks parameters in tie_break_order ascending from first entry to last. For each parameter, delta equals span times step_fraction where span is max minus min for that parameter. Form two clamped candidates at base minus delta and base plus delta while holding other parameters fixed, where each clamp is min of max and the greater of min and the candidate. Evaluate combined RMSE for the active split_group at each candidate. Select the candidate with the lowest RMSE among the two. Accept that value only when its RMSE is strictly less than the pass RMSE before this parameter step; otherwise restore base before advancing. Do not stop at the first improving candidate when the other candidate is better.

The pass RMSE before this parameter step is the running combined RMSE carried into this parameter: it already reflects every earlier parameter accepted in the same pass, and it is not a single RMSE frozen at the start of the pass. When a candidate is accepted, update that running RMSE to the accepted candidate's combined RMSE before advancing to the next parameter, so a later parameter is judged against the improved value. Predicted Id and Cgg use round12 as above, but this running combined RMSE stays unrounded throughout the walk.

An outer iteration is one full pass over tie_break_order in ascending order. Increment the outer iteration counter at the start of each pass before evaluating stop conditions. Always complete at least one full outer pass even when the initial combined RMSE is already at or below convergence_rmse. After a completed pass, stop when that pass made no improvement or the combined RMSE then falls below convergence_rmse. Do not treat a pre-pass RMSE check as a completed iteration of zero, and do not skip the first pass when the starting parameters already reproduce a group's measurements. Report the maximum outer iteration count and maximum final combined RMSE across split groups in convergence metadata. The reported iterations value is therefore always at least one whenever any group is fitted, and convergence.final_rmse is the maximum of the per-group final combined RMSE values.

When TB3_GAA_BOUNDS_ROOT points at an absolute directory, model-fit ignores the --bounds file path for that invocation and loads only parameter_bounds.toml from that overlay directory.





