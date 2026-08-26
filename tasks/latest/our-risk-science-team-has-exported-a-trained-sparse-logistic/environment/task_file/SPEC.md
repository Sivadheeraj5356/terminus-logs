# Sparse Logistic Horizon Risk Model Specification

This task is an offline inference and calibration audit for a trained sparse logistic risk model. The files under `/app/task_file/model` are model artifacts: feature normalization statistics, drift adjustments, horizon-window gates, pairwise interaction weights, segment priors, calibration bands, monotonic post-calibration rules, and label thresholds.

The evaluator entrypoint `/app/task_file/calibrator.py` must accept exactly one command-line argument: the task root directory. For the bundled task this is `/app/task_file`. It reads `/app/task_file/model/*.csv` and `/app/task_file/input/requests.bin`, creates `/app/task_file/output` if needed, and writes twelve model-audit reports: `/app/task_file/output/predictions.csv`, `/app/task_file/output/feature_trace.csv`, `/app/task_file/output/segment_summary.csv`, `/app/task_file/output/record_diagnostics.csv`, `/app/task_file/output/interaction_trace.csv`, `/app/task_file/output/monotonic_audit.csv`, `/app/task_file/output/horizon_stability.csv`, `/app/task_file/output/feature_ablation.csv`, `/app/task_file/output/policy_frontier.csv`, `/app/task_file/output/rank_corridor.csv`, `/app/task_file/output/resilient_frontier.csv`, and `/app/task_file/output/pairwise_ablation.csv`.

## Batch Request Format

`/app/task_file/input/requests.bin` is little-endian. The file begins with:

- 4 bytes magic: ASCII `SHRC`.
- `u8` version, currently `1`.
- `u32` record count.

Each record then contains:

- `u32 record_id`.
- `u8 segment`.
- `u16 horizon_days`.
- `u16 observation_count`.
- For each observation: `u16 feature_id`, followed by `f64 value`.

The file is malformed if the magic or version is wrong, any declared field is truncated, or trailing bytes remain after the declared records. For malformed input the scorer must exit nonzero and must not leave any of the twelve required output CSV files behind.

## Trained Model Artifacts

All CSV files have a header row. No quoted commas appear in the bundled model files.

`features.csv` columns:

- `feature_id`: integer feature id.
- `name`: emitted feature name.
- `mean`: base mean.
- `scale`: base scale.
- `weight`: base linear weight.
- `missing_value`: default raw value when a feature is absent.
- `clip_low`, `clip_high`: inclusive clipping bounds after normalization.
- `group`: informational group name; it is not emitted.

`feature_drifts.csv` columns:

- `segment`, `feature_id`, `per_day_delta`.
- Missing drift rows mean `0.0`.

`segments.csv` columns:

- `segment`, `bias`, `temperature`, `prior_logit`.
- If `temperature` is `0.0`, use `1.0` instead.

`horizon_windows.csv` columns:

- `segment`, `feature_id`, `min_horizon`, `max_horizon`, `scale_multiplier`, `weight_delta`, `missing_override`, `gate`.
- A row matches when `segment` and `feature_id` match the request and feature, and `min_horizon <= horizon_days < max_horizon`.
- Only the first matching row in file order is used.
- Empty `missing_override` means keep the feature's `missing_value`; a nonempty value replaces it only when the feature is absent from the request.
- `gate=0` forces the final normalized magnitude to zero while preserving the sign of the normalized value computed immediately before gating. For example, a pre-gate normalized value of `-2.5` becomes `-0.0`; a pre-gate normalized value of `2.5` becomes `0.0`. The linear contribution is then computed from that signed zero and `weight + weight_delta`.
- If no row matches, use `scale_multiplier=1.0`, `weight_delta=0.0`, no missing override, and `gate=1`.
- `window_index` in the trace is the zero-based row index within `horizon_windows.csv`, excluding the header, or `-1` when no row matches.

`interactions.csv` columns:

- `segment`, `feature_a`, `feature_b`, `weight`.
- `segment=-1` applies to every segment. Rows for the exact segment and rows for `-1` both apply.
- An interaction adds `normalized(feature_a) * normalized(feature_b) * weight` to the record logit after all linear features have been processed.

`calibration.csv` columns:

- `segment`, `lower`, `upper`, `multiplier`, `addend`.
- Calibration rows are checked in file order for the request segment.
- The first row with `lower <= raw_probability < upper` is used, except an `upper` value of exactly `1.0` is inclusive.
- If no calibration row matches, use multiplier `1.0`, addend `0.0`, and calibration band `-1`.
- `calibration_band` in `predictions.csv` is the zero-based row index within all rows for that segment, excluding rows for other segments.

`monotonic_rules.csv` columns:

- `rule_id`: integer id emitted in `monotonic_audit.csv`.
- `segment`, `feature_id`, `min_horizon`, `max_horizon`.
- `direction`: either `asc` or `desc`.
- `strength`: floating-point blend factor in `[0.0, 1.0]`.
- A rule matches a record when the record's segment matches, `min_horizon <= horizon_days < max_horizon`, and `feature_id` is a known model feature. Every record is assigned to at most one monotonic rule: the first matching row in `monotonic_rules.csv` file order. Records with no matching rule keep the calibrated score unchanged.

`thresholds.csv` has one data row:

- `review_threshold`, `high_threshold`.
- Final label is `LOW` when `score < review_threshold`, `REVIEW` when `review_threshold <= score < high_threshold`, and `HIGH` otherwise.

## Inference And Calibration Rules

For each request, duplicate observations for a known feature use the last value in request order. Observations for unknown feature ids are ignored for scoring but counted in `unknown_observation_count` only internally; they do not produce trace rows. The emitted `feature_trace.csv` contains one row for every known model feature for every record, including absent features.

For each known feature:

1. Start with the last observed raw value. If absent, start with `missing_value`, or the first matching window's `missing_override` when it is nonempty.
2. Compute the drifted center as `mean + horizon_days * per_day_delta` for the request segment and feature.
3. Compute effective scale as `scale * scale_multiplier`. If the effective scale is `0.0`, the normalized value is `0.0`; otherwise it is `(raw_value - drifted_center) / effective_scale`.
4. Clamp the normalized value to the inclusive `[clip_low, clip_high]` range.
5. If the selected window has `gate=0`, replace the normalized value with signed zero using the sign of the clamped normalized value from step 4.
6. The linear contribution is normalized value times `weight + weight_delta`.

The record logit is:

`segment.bias + segment.prior_logit + sum(linear contributions) + sum(pair interaction contributions)`

The raw probability is `1 / (1 + exp(-logit / temperature))`, using temperature `1.0` when the segment temperature is `0.0`. Apply the first matching calibration band to get `calibrated_score = raw_probability * multiplier + addend`, then clamp `calibrated_score` to `[0.0, 1.0]`.

After every record has a calibrated score, apply monotonic post-calibration rules:

1. Assign each record to the first matching row in `monotonic_rules.csv`, or no rule when no row matches.
2. For each rule independently, rank assigned records by the rule feature's final normalized value from the feature-inference pass. For `direction=asc`, sort normalized values ascending; for `direction=desc`, sort normalized values descending. Ties are broken by `record_id` ascending, then original input order ascending. The rank is zero-based within that rule.
3. Run unweighted pool-adjacent-violators isotonic fitting over calibrated scores in rank order, enforcing a nondecreasing fitted score sequence in that rank order. Start with one pool per record. Whenever a pool's mean is greater than the following pool's mean, merge those adjacent pools and replace their mean with the arithmetic mean of all calibrated scores in the merged pool. Continue until no adjacent violation remains. Every record's fitted score is the final mean of its pool.
4. The final `score` is `clamp(calibrated_score * (1 - strength) + fitted_score * strength, 0.0, 1.0)`. Records with no monotonic rule use `fitted_score = calibrated_score` and final `score = calibrated_score`.
5. Final risk labels, prediction ordering, segment summaries, and `record_diagnostics.csv` `score_delta` all use the post-monotonic final `score`. `calibration_band` continues to describe the pre-monotonic calibration band.

## Model Audit Reports

### Scenario Naming Conventions

Several reports compare the base batch with globally rerun counterfactual batches. Scenario names are exact string values:

- `base`: the normal unmodified request batch.
- `minus_7`: every record's horizon is shifted by `-7` and clamped with `max(0, horizon_days - 7)`.
- `plus_7`: every record's horizon is shifted by `+7` and clamped with `min(60, horizon_days + 7)`.
- `ablated_<feature_id>`: a single-feature ablation. The prefix is exactly `ablated_` with a trailing `d`; `ablate_<feature_id>` is wrong.
- `pair_ablated_<feature_a>_<feature_b>`: a pairwise feature ablation for two known feature ids with `feature_a < feature_b`. The word `ablated` again includes the trailing `d`.

Every counterfactual scenario is global: build the whole modified request batch, then rerun feature inference, interactions, calibration, monotonic pooling, labels, and prediction sorting over that entire batch. Do not score perturbed records one at a time against base-batch monotonic pools or base ranks.

`predictions.csv` header:

`record_id,segment,horizon_days,score,label,calibration_band`

Rows are sorted by unrounded `score` descending, then `record_id` ascending. `score` is formatted with exactly six digits after the decimal point.

`feature_trace.csv` header:

`record_id,feature_id,feature_name,used_missing,window_index,normalized,linear_contribution`

Rows are grouped in the same record order used by `predictions.csv`. Within each record, rows are sorted by absolute unrounded `linear_contribution` descending, then `feature_id` ascending. `used_missing` is `1` when the feature was absent from the request and `0` otherwise. `normalized` and `linear_contribution` are formatted with exactly six digits after the decimal point.

Floating-point formatting must preserve the sign of computed trace zero values. If arithmetic produces negative zero for `normalized` or `linear_contribution`, emit `-0.000000`; do not normalize it to `0.000000`.

`segment_summary.csv` header:

`segment,record_count,avg_score,max_score,top_record_id,low_count,review_count,high_count,calibration_bands,missing_feature_count,unknown_observation_count,duplicate_known_observation_count,dominant_feature_id,dominant_feature_abs_contribution,signed_zero_trace_count`

Rows are sorted by `segment` ascending and include one row for every segment that appears in the request records. If there are zero records, emit only the header.

For each segment:

- `record_count` is the number of request records for that segment.
- `avg_score` is the arithmetic mean of unrounded final scores for the segment, formatted with exactly six digits after the decimal point.
- `max_score` is the maximum unrounded final score for the segment, formatted with exactly six digits after the decimal point.
- `top_record_id` is the record id of the segment record with the highest unrounded score, breaking ties by smaller `record_id`.
- `low_count`, `review_count`, and `high_count` count final labels in that segment.
- `calibration_bands` is a semicolon-separated list of `band:count` entries sorted by numeric band id ascending, including `-1` when records in the segment used no calibration band.
- `missing_feature_count` is the total number of emitted trace rows in the segment with `used_missing = 1`.
- `unknown_observation_count` counts every observation whose feature id is not present in `features.csv`, including repeated unknown feature ids.
- `duplicate_known_observation_count` counts extra observations for known features within each record after the last-value rule. For example, three observations for the same known feature in one record contribute `2`.
- `dominant_feature_id` is the known feature id with the largest sum of absolute unrounded `linear_contribution` values over all trace rows in the segment, breaking ties by smaller feature id.
- `dominant_feature_abs_contribution` is that winning sum, formatted with exactly six digits after the decimal point.
- `signed_zero_trace_count` is the number of trace rows in the segment where either `normalized` or `linear_contribution` is a negative zero before formatting.

`record_diagnostics.csv` header:

`record_id,segment,horizon_days,input_order,raw_logit,temperature,raw_probability,score_delta,interaction_count,interaction_contribution_sum,top_positive_feature_id,top_positive_contribution,top_negative_feature_id,top_negative_contribution`

Rows are grouped in the same record order used by `predictions.csv`.

For each record:

- `input_order` is the zero-based record position in `requests.bin` before prediction sorting.
- `raw_logit` is the final logit after segment bias, prior logit, all linear feature contributions, and all interaction contributions, before temperature scaling. Format with exactly six digits after the decimal point.
- `temperature` is the effective segment temperature after replacing `0.0` with `1.0`. Format with exactly six digits after the decimal point.
- `raw_probability` is `sigmoid(raw_logit / temperature)` before calibration. Format with exactly six digits after the decimal point.
- `score_delta` is final post-monotonic `score - raw_probability` after calibration, monotonic pooling, blending, and score clamping. Format with exactly six digits after the decimal point.
- `interaction_count` is the number of interaction rows applied to that record.
- `interaction_contribution_sum` is the unrounded sum of all applied interaction contributions for that record. Format with exactly six digits after the decimal point.
- `top_positive_feature_id` is the feature id with the largest positive unrounded linear contribution, breaking ties by smaller feature id. If no linear contribution is positive, emit `-1`.
- `top_positive_contribution` is that winning positive contribution, or `0.000000` when `top_positive_feature_id` is `-1`.
- `top_negative_feature_id` is the feature id with the most negative unrounded linear contribution, breaking ties by smaller feature id. If no linear contribution is negative, emit `-1`.
- `top_negative_contribution` is that winning negative contribution, or `0.000000` when `top_negative_feature_id` is `-1`.

`interaction_trace.csv` header:

`record_id,interaction_index,segment_scope,feature_a,feature_b,normalized_a,normalized_b,weight,contribution`

Rows are grouped in the same record order used by `predictions.csv`. Within each record, emit applicable interactions in `interactions.csv` file order.

For each interaction row whose `segment` is `-1` or the request segment:

- `interaction_index` is the zero-based row index within `interactions.csv`, excluding the header.
- `segment_scope` is the interaction row's `segment` value, including `-1` for global rows.
- `normalized_a` and `normalized_b` are the final normalized feature values used by the interaction after missing values, drift, window selection, clamping, and gating. Format both with exactly six digits after the decimal point.
- `weight` is the interaction row weight, formatted with exactly six digits after the decimal point.
- `contribution` is `normalized_a * normalized_b * weight`, formatted with exactly six digits after the decimal point.

`monotonic_audit.csv` header:

`record_id,rule_id,rank,pool_start_rank,pool_end_rank,ordering_value,calibrated_score,fitted_score,final_score`

Rows are grouped in the same record order used by `predictions.csv`.

For each record:

- `rule_id` is the matching monotonic rule id, or `-1` when no rule matched.
- `rank` is the record's zero-based rank within its assigned rule after applying the rule's direction and tie-breakers, or `-1` when no rule matched.
- `pool_start_rank` and `pool_end_rank` are the inclusive zero-based rank span of the isotonic pool that produced the fitted score, or `-1` and `-1` when no rule matched.
- `ordering_value` is the rule feature's final normalized value used for ranking, formatted with exactly six digits after the decimal point. Emit `0.000000` when no rule matched.
- `calibrated_score` is the post-calibration, pre-monotonic score, formatted with exactly six digits after the decimal point.
- `fitted_score` is the isotonic pool fitted score before strength blending, formatted with exactly six digits after the decimal point.
- `final_score` is the final post-monotonic score, formatted with exactly six digits after the decimal point. It must equal the `score` emitted for the same record in `predictions.csv`.

`horizon_stability.csv` header:

`record_id,base_horizon,scenario,scenario_horizon,scenario_rank,scenario_score,scenario_label,score_delta,rank_delta,rule_id,pool_start_rank,pool_end_rank`

This report measures horizon sensitivity after global monotonic pooling. First compute the normal base outputs and base prediction rank, where rank is the zero-based row position in `predictions.csv` after sorting. Then evaluate two scenario batches:

- `minus_7`: every request record's `horizon_days` is replaced by `max(0, horizon_days - 7)`.
- `plus_7`: every request record's `horizon_days` is replaced by `min(60, horizon_days + 7)`.

For each scenario, rerun the complete feature inference, drift, horizon-window selection, interactions, calibration, monotonic rule assignment, isotonic pooling, strength blending, label assignment, and prediction sorting over the entire scenario batch. The scenario is not a per-record isolated perturbation: all records are shifted together, so monotonic pools and ranks may change because other records moved.

Rows are grouped by the base prediction order used by `predictions.csv`; for each base record emit `minus_7` first and `plus_7` second. `scenario_rank` is that record's zero-based prediction rank in the scenario batch. `scenario_score` and `scenario_label` are the scenario final score and label. `score_delta` is `scenario_score - base_score` using raw unrounded final scores before formatting. `rank_delta` is `scenario_rank - base_rank`. `rule_id`, `pool_start_rank`, and `pool_end_rank` are the scenario monotonic audit fields for that record, or `-1`, `-1`, `-1` when no scenario monotonic rule matched.

`feature_ablation.csv` header:

`feature_id,record_count,avg_score_delta,max_abs_delta,top_record_id,label_flip_count,rank_displacement_sum,dominant_segment`

This report measures global feature sensitivity after monotonic pooling. Emit one row for every known model feature sorted by numeric `feature_id`. For one feature row, build a scenario named exactly `ablated_<feature_id>` by removing every observation with that `feature_id` from every request record before duplicate handling; the ablated feature is then treated as absent and follows the normal missing-value, horizon-window override, drift, gating, linear, interaction, calibration, monotonic, label, and prediction-sort rules. Unknown observations and all other known observations remain unchanged. Rerun the complete scoring pipeline over the entire ablation batch for each feature independently.

Compare each ablation scenario against the base final outputs using raw unrounded final scores and prediction ranks. `record_count` is the number of request records. `avg_score_delta` is the arithmetic mean of `scenario_score - base_score` over all records. `max_abs_delta` is the largest absolute raw score delta. `top_record_id` is the record with the largest absolute raw score delta, breaking ties by larger signed delta, then smaller `record_id`. `label_flip_count` counts records whose scenario label differs from the base label. `rank_displacement_sum` is the sum over records of `abs(scenario_rank - base_rank)`. `dominant_segment` is the base segment whose records have the largest sum of absolute raw score deltas, breaking ties by smaller segment id. If the request batch is empty, emit one row per known feature with `record_count=0`, all numeric deltas and counts zero, `top_record_id=-1`, and `dominant_segment=-1`.

`pairwise_ablation.csv` header:

`feature_a,feature_b,record_count,avg_synergy,max_abs_synergy,top_record_id,interaction_label_flip_count,rank_synergy_sum,dominant_segment`

This report measures second-order, non-additive effects between pairs of known features after global monotonic pooling. Emit one row for every unordered pair of known model features, sorted by numeric `feature_a` ascending, then numeric `feature_b` ascending, with `feature_a < feature_b`.

For one row, build a pairwise scenario named exactly `pair_ablated_<feature_a>_<feature_b>` by removing every observation whose feature id is either `feature_a` or `feature_b` from every request record before duplicate handling. Unknown observations and all other known observations remain unchanged. Rerun the complete scoring pipeline over the entire pairwise ablation batch.

The pairwise report also needs the two single-feature scenarios `ablated_<feature_a>` and `ablated_<feature_b>` for the same base batch. If those single scenarios were already computed for `feature_ablation.csv`, reuse them only if they are full global reruns. For each record:

- `base_score` is the base final score.
- `delta_a = score(ablated_<feature_a>) - base_score`.
- `delta_b = score(ablated_<feature_b>) - base_score`.
- `pair_delta = score(pair_ablated_<feature_a>_<feature_b>) - base_score`.
- `synergy = pair_delta - delta_a - delta_b`.
- `rank_interaction = (rank(pair_ablated_<feature_a>_<feature_b>) - base_rank) - (rank(ablated_<feature_a>) - base_rank) - (rank(ablated_<feature_b>) - base_rank)`.

For each feature pair:

- `record_count` is the number of request records.
- `avg_synergy` is the arithmetic mean of raw unrounded `synergy` over all records, formatted with six digits after the decimal point.
- `max_abs_synergy` is the largest absolute raw `synergy`, formatted with six digits after the decimal point.
- `top_record_id` is the record with the largest absolute raw `synergy`, breaking ties by larger signed `synergy`, then smaller `record_id`.
- `interaction_label_flip_count` counts records whose pairwise-ablation label differs from the base label while both single-feature ablation labels remain equal to the base label.
- `rank_synergy_sum` is the sum over records of `abs(rank_interaction)`.
- `dominant_segment` is the base segment whose records have the largest sum of absolute raw `synergy`, breaking ties by smaller segment id.

If the request batch is empty, emit one row per unordered known-feature pair with `record_count=0`, `avg_synergy=0.000000`, `max_abs_synergy=0.000000`, `top_record_id=-1`, `interaction_label_flip_count=0`, `rank_synergy_sum=0`, and `dominant_segment=-1`.

`policy_frontier.csv` header:

`budget,total_alerts,total_score_capture,threshold_plan,alert_segments`

This report builds an optimal segment-threshold policy frontier from the base final post-monotonic scores. Let the base prediction rank and labels remain unchanged; this report uses only final raw scores and segments. For each segment that appears in at least one request record, build candidate thresholds from that segment's distinct raw final scores plus sentinel `1.000001`. For a threshold, a record in that segment is selected when its raw final score is `>= threshold`; the candidate's `alerts` is the selected record count, and `score_capture` is the sum of selected raw final scores. Distinct candidate thresholds that produce the same `alerts` are all allowed because tie-breaking may choose different threshold plans.

Emit one row for every integer `budget` from `0` through the total record count inclusive. For each budget, choose exactly one candidate threshold per present segment to maximize total `score_capture` subject to total `alerts <= budget`. Ties choose larger `total_alerts`, then the lexicographically smallest threshold-plan string after formatting each threshold with six decimals. `threshold_plan` is a semicolon-separated list of `segment:threshold` entries for every present segment sorted by segment id. `alert_segments` is a semicolon-separated list of `segment:alerts` entries for segments with nonzero alerts sorted by segment id, or an empty field when total alerts is zero. `total_score_capture` is formatted with six digits after the decimal point. If the request batch is empty, emit only the header.

`rank_corridor.csv` header:

`record_id,base_rank,best_rank,worst_rank,rank_span,label_set,dominates_count,dominated_by_count,longest_dominance_chain,chain_terminal_record`

This report measures whether ranking relationships survive every single-feature global counterfactual scenario. Build the scenario set from the base batch, the two horizon-stability batches (`minus_7` and `plus_7`), and one feature-ablation batch per known model feature named `ablated_<feature_id>` in ascending feature id order. Each scenario must be rerun through the complete scoring pipeline, including feature inference, interactions, calibration, monotonic pooling, label assignment, and prediction sorting. A rank is the zero-based row position in that scenario's sorted predictions.

Rows are grouped in the base `predictions.csv` order. For each base record:

- `base_rank` is its rank in the base predictions.
- `best_rank` and `worst_rank` are the minimum and maximum rank observed for the record across all scenarios, including base.
- `rank_span` is `worst_rank - best_rank`.
- `label_set` is the semicolon-separated set of labels observed for the record across all scenarios, sorted in the order `LOW`, `REVIEW`, `HIGH`.
- Record A strictly dominates record B when A's rank is lower than B's rank in every scenario in the scenario set. `dominates_count` is the number of other records strictly dominated by this record. `dominated_by_count` is the number of other records that strictly dominate this record.
- The strict-dominance graph is acyclic. `longest_dominance_chain` is the maximum number of records in a path that starts at this record and follows strict-dominance edges. If several longest paths exist, choose the path whose full list of record ids is lexicographically smallest. `chain_terminal_record` is the final record id in the chosen path. A record with no outgoing strict-dominance edges has `longest_dominance_chain=1` and `chain_terminal_record` equal to its own `record_id`.

If the request batch is empty, emit only the header.

`resilient_frontier.csv` header:

`budget,worst_alerts,max_alerts,worst_score_capture,avg_score_capture,alert_volatility,binding_scenarios,threshold_plan`

This report builds a robust segment-threshold policy under the same single-feature scenario set used by `rank_corridor.csv`: `base`, `minus_7`, `plus_7`, and one `ablated_<feature_id>` scenario for every known model feature in ascending feature id order. Pairwise scenarios from `pairwise_ablation.csv` are not part of this robust frontier scenario set. Each included scenario must be rerun through the full scoring pipeline before policy construction.

For every segment present in the base batch, build candidate thresholds from the union of distinct raw final scores for that segment across all scenarios plus sentinel `1.000001`. A threshold plan chooses exactly one threshold for every base-present segment. In a scenario, a record is alerted when its scenario raw final score is greater than or equal to the chosen threshold for its segment. For each threshold plan and scenario, compute `scenario_alerts` and `scenario_score_capture`.

Emit one row for every integer `budget` from `0` through the base record count inclusive. A threshold plan is feasible for a budget only when its maximum `scenario_alerts` across all scenarios is less than or equal to that budget. Among feasible plans choose the one that:

1. Maximizes `worst_score_capture`, the minimum `scenario_score_capture` across scenarios.
2. Then maximizes `avg_score_capture`, the arithmetic mean of `scenario_score_capture` across scenarios.
3. Then maximizes `worst_alerts`, the minimum `scenario_alerts` across scenarios.
4. Then minimizes `alert_volatility`, equal to maximum `scenario_alerts` minus minimum `scenario_alerts`.
5. Then chooses the lexicographically smallest `threshold_plan` after formatting thresholds with six decimals.

`binding_scenarios` is the semicolon-separated list of scenario names whose raw `scenario_score_capture` equals the chosen plan's `worst_score_capture`, in scenario-set order. Single-feature ablation names in this field must use `ablated_<feature_id>` exactly. `threshold_plan` is a semicolon-separated list of `segment:threshold` entries for every base-present segment sorted by segment id. Format `worst_score_capture` and `avg_score_capture` with six digits after the decimal point. If the request batch is empty, emit only the header.

All twelve CSV files must contain the header even when there are zero records. All twelve files must end with exactly one trailing newline.
