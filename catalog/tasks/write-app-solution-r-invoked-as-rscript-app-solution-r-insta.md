# Write /app/solution.R, invoked as Rscript /app/solution.R <instance_dir> <output

Submission: `ebc3d639-ab70-43a1-92dd-38f9793fb75f`  
Slug: `write-app-solution-r-invoked-as-rscript-app-solution-r-insta`  
Latest archive: `ebc3d639-ab70-43a1-92dd-38f9793fb75f_submission_2026-07-16T19_03_47.091Z.zip`  
Revisions: 1

## Task summary

Write /app/solution.R, invoked as Rscript /app/solution.R <instance_dir> <output_path>. Read every input from <instance_dir> and write the result CSV to <output_path>. Schemas: measured_runs.csv has run_id,trial_key,case_id,run_in_case,elapsed_min,depth_mm,feed_mm_rev,material_code,material_label,depth_level,feed_level,condition_family,wear_mm,current_dc_mean,current_dc_range,current_ac_rms,vibration_table_rms,acoustic_spindle_rms,precision_weight; candidate_runs.csv replaces run_id with candidate_id. Other files are candidate_costs.csv(candidate_id,cost), design_limits.csv(required_new_runs,budget,max_per_case,max_per_condition_family,min_materials,min_depth_levels,min_feed_levels,rank_tolerance,tie_abs_tolerance,tie_rel_tolerance), quota_rules.csv(column,value,min_selected,max_selected), pair_rules.csv(rule_type,left_candidate_id,right_candidate_id), stress_scenarios.csv(scenario_id,regret_weight), precision_rules.csv(scenario_id,column,value,multiplier), dropout_rules.csv(scenario_id,candidate_id), scaling.csv(variable,center,scale), model_terms.csv(term), target_contrasts.csv(target_id,term,coefficient), and target_weights.csv(target_id,target_weight).

Required artifacts include: `/app/solution.R`.

Author anonymous tagged this **unknown** scientific-computing task (experimental-design, l-optimality, information-matrix, weighted-design, robust-design, minimax-regret).

Time estimates: expert ~300 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `ebc3d639-ab70-43a1-92dd-38f9793fb75f_submission_2026-07-16T19_03_47.091Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
