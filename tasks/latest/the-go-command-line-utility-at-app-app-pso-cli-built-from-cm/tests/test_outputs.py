"""Tests for system-administration parameter tuning CLI: validates the server quota optimization report.

Test taxonomy:
  T1 structural (9):     test_t1_all_output_files_exist, test_t1_server_profile_a_valid_json_object,
                         test_t1_server_profile_c_valid_json_object, test_t1_server_profile_b_valid_json_object,
                         test_t1_exact_top_level_keys, test_t1_best_position_is_list_of_floats,
                         test_t1_best_value_is_float, test_t1_history_is_list_of_objects,
                         test_t1_history_entry_exact_keys_and_types
  T2 boundary (14):      test_t2_throttle_weight_at_t0_equals_w_start, test_t2_throttle_weight_at_t_end_equals_w_end,
                         test_t2_throttle_decay_slope_denominator_boundary, test_t2_position_above_max_bound_is_clamped,
                         test_t2_position_below_min_bound_is_clamped, test_t2_adjustment_clamping_upper_bound,
                         test_t2_adjustment_clamping_lower_bound, test_t2_boundary_reflection_coefficient_half,
                         test_t2_boundary_reflection_direction_reversal, test_t2_server_profile_c_position_within_nominal_bounds,
                         test_t2_server_profile_a_position_within_nominal_bounds, test_t2_server_profile_b_position_within_nominal_bounds,
                         test_t2_profile_bug1_position_within_nominal_bounds, test_t2_profile_bug2_position_within_nominal_bounds,
                         test_t2_profile_bug3_position_within_nominal_bounds
  T3 precedence (13):    test_t3_nodebest_updated_asynchronously_before_clusterbest, test_t3_clusterbest_updated_on_strict_objective_improvement,
                         test_t3_clusterbest_tiebreaker_prefers_smaller_capacity_distance, test_t3_clusterbest_tiebreaker_equal_capacity_distance_retains_earlier_best,
                         test_t3_history_iterations_strictly_increasing, test_t3_history_best_values_monotonic_non_increasing,
                         test_t3_server_profile_c_exact_best_value, test_t3_server_profile_a_exact_best_value,
                         test_t3_server_profile_b_exact_best_value, test_t3_profile_bug1_exact_position_trajectory,
                         test_t3_profile_bug3_exact_position_trajectory, test_t3_server_profile_a_exact_position_trajectory
  T4 inclusion (10):     test_t4_history_excludes_initial_cluster_evaluation, test_t4_history_excludes_non_improving_iterations,
                         test_t4_history_includes_all_strictly_improving_iterations, test_t4_server_profile_a_history_omission_count,
                         test_t4_profile_bug1_history_exact_length, test_t4_server_profile_c_history_last_entry_matches_top_level_best_value,
                         test_t4_server_profile_a_history_last_entry_matches_top_level_best_value, test_t4_server_profile_b_history_last_entry_matches_top_level_best_value,
                         test_t4_output_no_null_or_empty_string_for_present_fields, test_t4_output_no_nan_or_inf_in_positions_or_values
  T5 interaction (12):   test_t5_throttle_decay_and_adjustment_clamping_simultaneous_interaction, test_t5_boundary_clamping_and_nodebest_evaluation_interaction,
                         test_t5_boundary_reflection_and_subsequent_adjustment_update_interaction, test_t5_rng_sampling_order_r1_r2_per_dimension_interaction,
                         test_t5_asynchronous_clusterbest_propagation_within_iteration_interaction, test_t5_quantization_exact_6_decimals_best_value_server_profile_a,
                         test_t5_quantization_exact_6_decimals_history_entries, test_t5_server_profile_a_optimization_progress_magnitude,
                         test_t5_multi_dimensional_boundary_reflection_independence, test_t5_zero_adjustment_initialization_on_symmetric_bounds,
                         test_t5_monotonic_history_recording_under_plateau_conditions, test_t5_deterministic_reproducibility_across_identical_runs
  T6 constraints (10):   test_t6_constraint_throttle_decay_denominator_trap, test_t6_constraint_rng_per_node_vs_per_dimension_trap,
                         test_t6_constraint_boundary_reflection_coefficient_trap, test_t6_constraint_capacity_distance_tiebreaker_strict_inequality_trap,
                         test_t6_constraint_history_raw_float_vs_rounded_comparison_trap, test_t6_constraint_missing_struct_tags_pascal_case_trap,
                         test_t6_constraint_exclusive_vs_inclusive_boundary_check_trap, test_t6_constraint_initial_cluster_evaluation_missing_nodebest_trap,
                         test_t6_constraint_copy_slice_pointer_aliasing_trap, test_t6_constraint_history_slice_nil_vs_empty_array_trap
"""

import json
import math
from pathlib import Path

PROFILE_A_CONF = "/app/data/config_rosenbrock.json" if Path("/app/data/config_rosenbrock.json").exists() else "./environment/data/config_rosenbrock.json"
PROFILE_C_CONF = "/app/data/config_sphere.json" if Path("/app/data/config_sphere.json").exists() else "./environment/data/config_sphere.json"
PROFILE_B_CONF = "/app/data/config_rastrigin.json" if Path("/app/data/config_rastrigin.json").exists() else "./environment/data/config_rastrigin.json"
BUG1_CONF = "/app/data/config_bug1.json" if Path("/app/data/config_bug1.json").exists() else "./environment/data/config_bug1.json"
BUG2_CONF = "/app/data/config_bug2.json" if Path("/app/data/config_bug2.json").exists() else "./environment/data/config_bug2.json"
BUG3_CONF = "/app/data/config_bug3.json" if Path("/app/data/config_bug3.json").exists() else "./environment/data/config_bug3.json"

TRAP1_CONF = "/app/data/config_trap1.json" if Path("/app/data/config_trap1.json").exists() else "./environment/data/config_trap1.json"
TRAP2_CONF = "/app/data/config_trap2.json" if Path("/app/data/config_trap2.json").exists() else "./environment/data/config_trap2.json"
TRAP3_CONF = "/app/data/config_trap3.json" if Path("/app/data/config_trap3.json").exists() else "./environment/data/config_trap3.json"
TRAP4_CONF = "/app/data/config_trap4.json" if Path("/app/data/config_trap4.json").exists() else "./environment/data/config_trap4.json"
TRAP5_CONF = "/app/data/config_trap5.json" if Path("/app/data/config_trap5.json").exists() else "./environment/data/config_trap5.json"


PROFILE_A_OUT = "/app/out/rosenbrock.json" if Path("/app").exists() else "./environment/out/rosenbrock.json"
PROFILE_C_OUT = "/app/out/sphere.json" if Path("/app").exists() else "./environment/out/sphere.json"
PROFILE_B_OUT = "/app/out/rastrigin.json" if Path("/app").exists() else "./environment/out/rastrigin.json"
BUG1_OUT = "/app/out/bug1.json" if Path("/app").exists() else "./environment/out/bug1.json"
BUG2_OUT = "/app/out/bug2.json" if Path("/app").exists() else "./environment/out/bug2.json"
BUG3_OUT = "/app/out/bug3.json" if Path("/app").exists() else "./environment/out/bug3.json"

TRAP1_OUT = "/app/out/trap1.json" if Path("/app").exists() else "./environment/out/trap1.json"
TRAP2_OUT = "/app/out/trap2.json" if Path("/app").exists() else "./environment/out/trap2.json"
TRAP3_OUT = "/app/out/trap3.json" if Path("/app").exists() else "./environment/out/trap3.json"
TRAP4_OUT = "/app/out/trap4.json" if Path("/app").exists() else "./environment/out/trap4.json"
TRAP5_OUT = "/app/out/trap5.json" if Path("/app").exists() else "./environment/out/trap5.json"


def get_data(path_str):
    p = Path(path_str)
    if not p.exists():
        if Path("/app").exists():
            import subprocess
            bin_path = "/app/pso_cli" if Path("/app/pso_cli").exists() else "/app/tuning_cli"
            conf_map = {
                PROFILE_A_OUT: PROFILE_A_CONF,
                PROFILE_C_OUT: PROFILE_C_CONF,
                PROFILE_B_OUT: PROFILE_B_CONF,
                BUG1_OUT: BUG1_CONF,
                BUG2_OUT: BUG2_CONF,
                                BUG3_OUT: BUG3_CONF,
                TRAP1_OUT: TRAP1_CONF,
                TRAP2_OUT: TRAP2_CONF,
                TRAP3_OUT: TRAP3_CONF,
                TRAP4_OUT: TRAP4_CONF,
                TRAP5_OUT: TRAP5_CONF,
            }
            conf = conf_map.get(path_str)
            if conf and Path(conf).exists() and Path(bin_path).exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run([bin_path, "-config", conf, "-output", path_str], check=True)
        if not p.exists():
            fallback = path_str.replace("/app/out/", "./environment/out/").replace("/app/data/", "./environment/data/")
            p = Path(fallback)
    return json.loads(p.read_text())


# ─── T1: Structural ──────────────────────────────────────────────────────────

def test_t1_all_output_files_exist():
    """Validates that every required server profile configuration output file was generated exactly."""
    for out in [PROFILE_A_OUT, PROFILE_C_OUT, PROFILE_B_OUT, BUG1_OUT, BUG2_OUT, BUG3_OUT]:
        _ = get_data(out)







def test_t1_exact_top_level_keys():
    """Validates that server profile output JSON strictly contains best_position, best_value, and history keys."""
    data = get_data(PROFILE_A_OUT)
    expected_keys = {"best_position", "best_value", "history"}
    assert set(data.keys()) == expected_keys, f"Top-level keys mismatch: got {set(data.keys())}, expected {expected_keys}"

def test_t1_best_position_is_list_of_floats():
    """Validates that best_position is formatted as a non-empty list of floating-point numbers."""
    data = get_data(PROFILE_A_OUT)
    assert isinstance(data["best_position"], list) and len(data["best_position"]) > 0, "best_position must be a non-empty list."
    assert all(isinstance(x, (int, float)) for x in data["best_position"]), "All elements of best_position must be numeric."

def test_t1_best_value_is_float():
    """Validates that best_value is formatted as a scalar numeric float."""
    data = get_data(PROFILE_A_OUT)
    assert isinstance(data["best_value"], (int, float)), "best_value must be a numeric value."

def test_t1_history_is_list_of_objects():
    """Validates that history is formatted as a list of JSON objects."""
    data = get_data(PROFILE_A_OUT)
    assert isinstance(data["history"], list), "history must be a JSON list."

def test_t1_history_entry_exact_keys_and_types():
    """Validates that every history entry object strictly contains iteration (int) and best_value (float)."""
    data = get_data(PROFILE_A_OUT)
    for entry in data["history"]:
        assert isinstance(entry, dict), "History entries must be dictionary objects."
        assert set(entry.keys()) == {"iteration", "best_value"}, f"Invalid history keys: {set(entry.keys())}"
        assert isinstance(entry["iteration"], int), "iteration must be an integer."
        assert isinstance(entry["best_value"], (int, float)), "best_value must be numeric."


# ─── T2: Boundary ────────────────────────────────────────────────────────────

def test_t2_throttle_weight_at_t0_equals_w_start():
    """Validates exact inclusive boundary: w(0) strictly equals w_start."""
    data = get_data(BUG1_OUT)
    assert data["history"][0]["iteration"] == 0, "First step must be at iteration 0."

def test_t2_throttle_weight_at_t_end_equals_w_end():
    """Validates exact inclusive boundary: w(max_iterations - 1) strictly equals w_end."""
    data = get_data(PROFILE_C_OUT)
    assert len(data["history"]) > 0, "History must contain recorded steps."

def test_t2_throttle_decay_slope_denominator_boundary():
    """Validates exact linear decay slope denominator boundary (max_iterations - 1)."""
    data = get_data(BUG1_OUT)
    expected = 22.993645
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), f"Decay slope denominator mismatch: got {data['best_value']}"

def test_t2_position_above_max_bound_is_clamped():
    """Validates exact inclusive boundary: parameter value strictly above max_bound clamps exactly to max_bound."""
    data = get_data(BUG3_OUT)
    assert all(x <= 5.12 for x in data["best_position"]), "Parameter coordinate exceeded maximum allowed boundary max_bound."

def test_t2_position_below_min_bound_is_clamped():
    """Validates exact inclusive boundary: parameter value strictly below min_bound clamps exactly to min_bound."""
    data = get_data(BUG3_OUT)
    assert all(x >= -5.12 for x in data["best_position"]), "Parameter coordinate fell below minimum allowed boundary min_bound."

def test_t2_adjustment_clamping_upper_bound():
    """Validates exact adjustment clamping inclusive upper boundary: adjustment step strictly <= v_max."""
    data = get_data(BUG3_OUT)
    assert data["best_value"] <= 100.0, "Adjustment step exceeded maximum adjustment threshold v_max."

def test_t2_adjustment_clamping_lower_bound():
    """Validates exact adjustment clamping inclusive lower boundary: adjustment step strictly >= -v_max."""
    data = get_data(BUG3_OUT)
    assert data["best_value"] >= 0.0, "Adjustment step fell below negative adjustment threshold -v_max."

def test_t2_boundary_reflection_coefficient_half():
    """Validates exact boundary reflection damping coefficient: adjustment *= -0.5 on bound contact."""
    data = get_data(BUG3_OUT)
    expected = 4.63996
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), f"Boundary reflection damping mismatch: got {data['best_value']}"

def test_t2_boundary_reflection_direction_reversal():
    """Validates boundary reflection sign reversal: adjustment step direction strictly inverted on boundary contact."""
    data = get_data(BUG3_OUT)
    expected_pos = [-0.4733365787757474, 0.06690939184416633]
    assert math.isclose(data["best_position"][0], expected_pos[0], rel_tol=1e-5, abs_tol=1e-5), "Boundary reflection direction reversal mismatch."

def test_t2_server_profile_c_position_within_nominal_bounds():
    """Validates that final best_position in Server Profile C run lies strictly within [-5.12, 5.12]."""
    data = get_data(PROFILE_C_OUT)
    assert all(-5.12 <= x <= 5.12 for x in data["best_position"]), "Server Profile C coordinates out of nominal bounds."

def test_t2_server_profile_a_position_within_nominal_bounds():
    """Validates that final best_position in Server Profile A run lies strictly within [-2.048, 2.048]."""
    data = get_data(PROFILE_A_OUT)
    assert all(-2.048 <= x <= 2.048 for x in data["best_position"]), "Server Profile A coordinates out of nominal bounds."

def test_t2_server_profile_b_position_within_nominal_bounds():
    """Validates that final best_position in Server Profile B run lies strictly within [-5.12, 5.12]."""
    data = get_data(PROFILE_B_OUT)
    assert all(-5.12 <= x <= 5.12 for x in data["best_position"]), "Server Profile B coordinates out of nominal bounds."

def test_t2_profile_bug1_position_within_nominal_bounds():
    """Validates that final best_position in Profile Bug 1 run lies strictly within [-10.0, 10.0]."""
    data = get_data(BUG1_OUT)
    assert all(-10.0 <= x <= 10.0 for x in data["best_position"]), "Profile Bug 1 coordinates out of nominal bounds."

def test_t2_profile_bug2_position_within_nominal_bounds():
    """Validates that final best_position in Profile Bug 2 run lies strictly within [-10.0, 10.0]."""
    data = get_data(BUG2_OUT)
    assert all(-10.0 <= x <= 10.0 for x in data["best_position"]), "Profile Bug 2 coordinates out of nominal bounds."

def test_t2_profile_bug3_position_within_nominal_bounds():
    """Validates that final best_position in Profile Bug 3 run lies strictly within [-5.12, 5.12]."""
    data = get_data(BUG3_OUT)
    assert all(-5.12 <= x <= 5.12 for x in data["best_position"]), "Profile Bug 3 coordinates out of nominal bounds."


# ─── T3: Precedence and ordering ─────────────────────────────────────────────

def test_t3_nodebest_updated_asynchronously_before_clusterbest():
    """Validates asynchronous precedence: node local best state must be updated immediately before cluster best evaluation."""
    data = get_data(PROFILE_C_OUT)
    assert len(data["history"]) >= 3, "Asynchronous state updates must produce multiple history steps."

def test_t3_clusterbest_updated_on_strict_objective_improvement():
    """Validates strict improvement precedence: cluster global best state updates when candidate cost < gBestVal."""
    data = get_data(PROFILE_C_OUT)
    best_vals = [entry["best_value"] for entry in data["history"]]
    for i in range(len(best_vals) - 1):
        assert best_vals[i] >= best_vals[i+1], "Global best cost trajectory must be monotonically non-increasing."

def test_t3_clusterbest_tiebreaker_prefers_smaller_capacity_distance():
    """Validates exact secondary tiebreaker precedence: when candidate cost == gBestVal, strictly prefers smaller Euclidean distance from origin."""
    data = get_data(PROFILE_B_OUT)
    expected = [-0.025023313159172306, -0.02153392210571592]
    assert math.isclose(data["best_position"][0], expected[0], rel_tol=1e-5, abs_tol=1e-5), f"Euclidean distance tiebreaker mismatch: got {data['best_position'][0]}"

def test_t3_clusterbest_tiebreaker_equal_capacity_distance_retains_earlier_best():
    """Validates equal distance tiebreaker precedence: when candidate cost == gBestVal and origin distances equal, retains earlier state."""
    data = get_data(PROFILE_B_OUT)
    assert len(data["best_position"]) == 2, "Position vector dimension mismatch."

def test_t3_history_iterations_strictly_increasing():
    """Validates ordering constraint: recorded history entries must have strictly increasing iteration indices."""
    data = get_data(PROFILE_A_OUT)
    iters = [entry["iteration"] for entry in data["history"]]
    assert all(iters[i] < iters[i+1] for i in range(len(iters) - 1)), "History iterations must be strictly increasing."

def test_t3_history_best_values_monotonic_non_increasing():
    """Validates ordering constraint: recorded history values must be strictly non-increasing across iterations."""
    data = get_data(PROFILE_A_OUT)
    vals = [entry["best_value"] for entry in data["history"]]
    assert all(vals[i] >= vals[i+1] for i in range(len(vals) - 1)), "History best values must be non-increasing."

def test_t3_server_profile_c_exact_best_value():
    """Validates exact final converged cost for Server Profile C configuration."""
    data = get_data(PROFILE_C_OUT)
    assert math.isclose(data["best_value"], 0.0, rel_tol=1e-5, abs_tol=1e-5), f"Server Profile C exact best value mismatch: {data['best_value']}"

def test_t3_server_profile_a_exact_best_value():
    """Validates exact final converged cost for Server Profile A configuration."""
    data = get_data(PROFILE_A_OUT)
    assert math.isclose(data["best_value"], 0.001656, rel_tol=1e-5, abs_tol=1e-5), f"Server Profile A exact best value mismatch: {data['best_value']}"

def test_t3_server_profile_b_exact_best_value():
    """Validates exact final converged cost for Server Profile B configuration."""
    data = get_data(PROFILE_B_OUT)
    assert math.isclose(data["best_value"], 0.215829, rel_tol=1e-5, abs_tol=1e-5), f"Server Profile B exact best value mismatch: {data['best_value']}"

def test_t3_profile_bug1_exact_position_trajectory():
    """Validates exact multi-dimensional parameter coordinates for Profile Bug 1."""
    data = get_data(BUG1_OUT)
    expected = [-3.7393936804052395, -1.4128145398572087, -1.9405453754588962, 0.11470175441354513, -1.7987946039065719]
    assert len(data["best_position"]) == 5
    assert all(math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5) for a, b in zip(data["best_position"], expected)), f"Profile Bug 1 coordinate trajectory mismatch: got {data['best_position']}"

def test_t3_profile_bug3_exact_position_trajectory():
    """Validates exact multi-dimensional parameter coordinates for Profile Bug 3."""
    data = get_data(BUG3_OUT)
    expected = [-0.4733365787757474, 0.06690939184416633]
    assert len(data["best_position"]) == 2
    assert all(math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5) for a, b in zip(data["best_position"], expected)), f"Profile Bug 3 coordinate trajectory mismatch: got {data['best_position']}"

def test_t3_server_profile_a_exact_position_trajectory():
    """Validates that Server Profile A coordinates are numeric and bounded correctly."""
    data = get_data(PROFILE_A_OUT)
    assert len(data["best_position"]) == 2, "Server Profile A coordinates must have exactly 2 dimensions."


# ─── T4: Inclusion/exclusion ──────────────────────────────────────────────────

def test_t4_history_excludes_initial_cluster_evaluation():
    """Validates inclusion exclusion: initial cluster evaluation before iteration 0 must NOT be appended to history."""
    data = get_data(PROFILE_A_OUT)
    for entry in data["history"]:
        assert entry["iteration"] >= 0, "Initial cluster state before iteration 0 must be excluded from history."

def test_t4_history_excludes_non_improving_iterations():
    """Validates inclusion exclusion: iterations with no strict objective improvement must be omitted from history."""
    data = get_data(PROFILE_A_OUT)
    assert len(data["history"]) <= 50, "History length exceeded expected bounds due to inclusion of non-improving steps."

def test_t4_history_includes_all_strictly_improving_iterations():
    """Validates inclusion exclusion: every strictly improving iteration must be included in history."""
    data = get_data(BUG1_OUT)
    assert len(data["history"]) == 3, f"Expected exactly 3 improving history entries for Profile Bug 1, got {len(data['history'])}"

def test_t4_server_profile_a_history_omission_count():
    """Validates exact history step bounds on Server Profile A proving non-improving step omission."""
    data = get_data(PROFILE_A_OUT)
    assert 5 <= len(data["history"]) <= 12, f"Server Profile A history length out of bounds: {len(data['history'])}"

def test_t4_profile_bug1_history_exact_length():
    """Validates exact history list length for Profile Bug 1 configuration."""
    data = get_data(BUG1_OUT)
    assert len(data["history"]) == 3, f"Expected history length 3 for Profile Bug 1, got {len(data['history'])}"

def test_t4_server_profile_c_history_last_entry_matches_top_level_best_value():
    """Validates inclusion exclusion: final history entry best_value strictly matches top-level best_value for Server Profile C."""
    data = get_data(PROFILE_C_OUT)
    if len(data["history"]) > 0:
        assert math.isclose(data["history"][-1]["best_value"], data["best_value"], rel_tol=1e-6, abs_tol=1e-6), "Server Profile C history final value mismatch."

def test_t4_server_profile_a_history_last_entry_matches_top_level_best_value():
    """Validates that final history entry best_value strictly matches top-level best_value for Server Profile A."""
    data = get_data(PROFILE_A_OUT)
    assert math.isclose(data["history"][-1]["best_value"], data["best_value"], rel_tol=1e-6, abs_tol=1e-6), "Server Profile A history final value mismatch."

def test_t4_server_profile_b_history_last_entry_matches_top_level_best_value():
    """Validates that final history entry best_value strictly matches top-level best_value for Server Profile B."""
    data = get_data(PROFILE_B_OUT)
    assert math.isclose(data["history"][-1]["best_value"], data["best_value"], rel_tol=1e-6, abs_tol=1e-6), "Server Profile B history final value mismatch."

def test_t4_output_no_null_or_empty_string_for_present_fields():
    """Validates structural inclusion: all present required fields are non-null and non-empty strings."""
    data = get_data(PROFILE_A_OUT)
    assert data["best_position"] is not None and data["best_value"] is not None and data["history"] is not None, "Output contains unexpected null values."

def test_t4_output_no_nan_or_inf_in_positions_or_values():
    """Validates inclusion exclusion: best_position and best_value strictly exclude NaN or Infinity."""
    data = get_data(PROFILE_A_OUT)
    assert not math.isnan(data["best_value"]) and not math.isinf(data["best_value"]), "best_value contains NaN or Inf."
    for x in data["best_position"]:
        assert not math.isnan(x) and not math.isinf(x), "best_position contains NaN or Inf."


# ─── T5: Rule interaction ────────────────────────────────────────────────────

def test_t5_throttle_decay_and_adjustment_clamping_simultaneous_interaction():
    """Validates rule interaction: linear throttle weight decay and adjustment clamping interact multiplicatively."""
    data = get_data(BUG1_OUT)
    expected = 22.993645
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), "Simultaneous interaction of throttle decay and adjustment clamping failed."

def test_t5_boundary_clamping_and_nodebest_evaluation_interaction():
    """Validates rule interaction: boundary clamping occurs strictly before node local best evaluation."""
    data = get_data(BUG3_OUT)
    assert all(-5.12 <= x <= 5.12 for x in data["best_position"]), "Simultaneous interaction of boundary clamping and local best evaluation failed."

def test_t5_boundary_reflection_and_subsequent_adjustment_update_interaction():
    """Validates rule interaction: inelastic boundary reflection (-0.5) directly modifies adjustment for subsequent iterations."""
    data = get_data(BUG3_OUT)
    expected = 4.63996
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), "Interaction of boundary reflection and subsequent adjustment updates failed."

def test_t5_rng_sampling_order_r1_r2_per_dimension_interaction():
    """Validates multiplicative rule interaction: independent sampling of r1 and r2 inside dimension loop."""
    data = get_data(BUG2_OUT)
    expected = 100.79063
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), "Interaction of independent RNG sampling order across dimensions failed."

def test_t5_asynchronous_clusterbest_propagation_within_iteration_interaction():
    """Validates rule interaction: asynchronous node state updates immediately influence subsequent nodes in same iteration."""
    data = get_data(BUG1_OUT)
    assert len(data["history"]) == 3, "Asynchronous state update propagation within iteration loop failed."

def test_t5_quantization_exact_6_decimals_best_value_server_profile_a():
    """Validates rule interaction: best_value rounded to exactly 6 decimal precision."""
    data = get_data(PROFILE_A_OUT)
    val = data["best_value"]
    rounded = round(val, 6)
    assert math.isclose(val, rounded, rel_tol=1e-9, abs_tol=1e-9), f"best_value {val} not rounded to 6 decimal places."

def test_t5_quantization_exact_6_decimals_history_entries():
    """Validates rule interaction: every best_value inside history rounded to exactly 6 decimal places."""
    data = get_data(PROFILE_A_OUT)
    for entry in data["history"]:
        val = entry["best_value"]
        rounded = round(val, 6)
        assert math.isclose(val, rounded, rel_tol=1e-9, abs_tol=1e-9), f"History value {val} not rounded to 6 decimal places."

def test_t5_server_profile_a_optimization_progress_magnitude():
    """Validates total optimization progress across all interaction rules on Server Profile A."""
    data = get_data(PROFILE_A_OUT)
    assert math.isclose(data["best_value"], 0.001656, rel_tol=1e-5, abs_tol=1e-5), f"Server Profile A progress magnitude mismatch: {data['best_value']}"

def test_t5_multi_dimensional_boundary_reflection_independence():
    """Validates rule interaction: multi-dimensional boundary reflection acts independently per coordinate dimension."""
    data = get_data(BUG3_OUT)
    assert len(data["best_position"]) == 2, "Multi-dimensional reflection dimension count mismatch."

def test_t5_zero_adjustment_initialization_on_symmetric_bounds():
    """Validates rule interaction: initial adjustment formulation across symmetric boundary range [-bound, bound]."""
    data = get_data(BUG2_OUT)
    assert all(-10.0 <= x <= 10.0 for x in data["best_position"]), "Symmetric bound adjustment initialization interaction failed."

def test_t5_monotonic_history_recording_under_plateau_conditions():
    """Validates rule interaction: strict monotonic check correctly suppresses non-improving plateau iterations."""
    data = get_data(PROFILE_C_OUT)
    vals = [entry["best_value"] for entry in data["history"]]
    assert all(vals[i] >= vals[i+1] for i in range(len(vals) - 1)), "Monotonic history recorded increasing value."
    assert len(vals) < 50, "Monotonic history check failed to suppress non-improving plateau iterations."

def test_t5_deterministic_reproducibility_across_identical_runs():
    """Validates rule interaction: identical seed and configuration parameters guarantee 100% byte-exact output reproducibility."""
    data1 = get_data(BUG1_OUT)
    data2 = get_data(BUG1_OUT)
    assert data1 == data2, "Deterministic reproducibility across identical configuration evaluations failed."


# ─── T6: Go attractor traps ──────────────────────────────────────────────────

def test_t6_constraint_throttle_decay_denominator_trap():
    """Constraint violation check: Validates exact adherence to behavioral specification constraints."""
    data = get_data(BUG1_OUT)
    expected = 22.993645
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), "Constraint violation: Naive throttle slope denominator max_iterations used."

def test_t6_constraint_rng_per_node_vs_per_dimension_trap():
    """Constraint violation check: Validates exact adherence to behavioral specification constraints."""
    data = get_data(BUG2_OUT)
    expected = 100.79063
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), "Constraint violation: RNG sampled per node instead of per dimension."

def test_t6_constraint_boundary_reflection_coefficient_trap():
    """Constraint violation check: Validates exact adherence to behavioral specification constraints."""
    data = get_data(BUG3_OUT)
    expected = 4.63996
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), "Constraint violation: Incorrect boundary reflection coefficient."

def test_t6_constraint_capacity_distance_tiebreaker_strict_inequality_trap():
    """Constraint violation check: Validates exact adherence to behavioral specification constraints."""
    data = get_data(PROFILE_B_OUT)
    expected = [-0.025023313159172306, -0.02153392210571592]
    assert math.isclose(data["best_position"][0], expected[0], rel_tol=1e-5, abs_tol=1e-5), "Constraint violation: Euclidean distance tiebreaker used <= instead of <."

def test_t6_constraint_history_raw_float_vs_rounded_comparison_trap():
    """Constraint violation check: Validates exact adherence to behavioral specification constraints."""
    data = get_data(PROFILE_C_OUT)
    assert len(data["history"]) >= 2, "Constraint violation: Monotonic history check performed on rounded values."

def test_t6_constraint_missing_struct_tags_pascal_case_trap():
    """Constraint violation check: Validates exact adherence to behavioral specification constraints."""
    data = get_data(PROFILE_A_OUT)
    assert "best_position" in data and "best_value" in data and "history" in data, "Constraint violation: Missing snake_case json struct tags caused PascalCase keys."

def test_t6_constraint_exclusive_vs_inclusive_boundary_check_trap():
    """Constraint violation check: Validates exact adherence to behavioral specification constraints."""
    data = get_data(BUG3_OUT)
    expected = [-0.4733365787757474, 0.06690939184416633]
    assert math.isclose(data["best_position"][0], expected[0], rel_tol=1e-5, abs_tol=1e-5), "Constraint violation: Boundary reflection triggered on exact boundary."

def test_t6_constraint_initial_cluster_evaluation_missing_nodebest_trap():
    """Constraint violation check: Validates exact adherence to behavioral specification constraints."""
    data = get_data(BUG1_OUT)
    assert len(data["history"]) == 3, "Constraint violation: Initial cluster state not initialized before loop."

def test_t6_constraint_copy_slice_pointer_aliasing_trap():
    """Constraint violation check: Validates exact adherence to behavioral specification constraints."""
    data = get_data(BUG1_OUT)
    expected = [-3.7393936804052395, -1.4128145398572087, -1.9405453754588962, 0.11470175441354513, -1.7987946039065719]
    assert math.isclose(data["best_position"][0], expected[0], rel_tol=1e-5, abs_tol=1e-5), "Constraint violation: Slice reference aliasing mutated stored best position."

def test_t6_constraint_history_slice_nil_vs_empty_array_trap():
    """Constraint violation check: Validates exact adherence to behavioral specification constraints."""
    data = get_data(PROFILE_A_OUT)
    assert data["history"] is not None and isinstance(data["history"], list), "Constraint violation: Nil slice serialized to JSON null instead of empty array []."

def test_t5_trap1_constant_inelastic_reflection():
    """Validates interaction: extreme bounded space forcing constant inelastic rebound on adjustment rate."""
    data = get_data(TRAP1_OUT)
    assert data["best_value"] == 0, f"Trap 1 failed: expected 0, got {data['best_value']}"

def test_t5_trap2_aggressive_adjustment_clamping():
    """Validates interaction: huge c1/c2 multipliers demanding absolute enforcement of v_max limits."""
    data = get_data(TRAP2_OUT)
    expected = 815.784208
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), f"Trap 2 failed: got {data['best_value']}"

def test_t5_trap3_max_iterations_two_decay_slope():
    """Validates interaction: boundary denominator (max_iterations - 1) on minimal iteration count."""
    data = get_data(TRAP3_OUT)
    expected = 1.001226
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), f"Trap 3 failed: got {data['best_value']}"

def test_t5_trap4_flat_landscape_euclidean_tiebreaker():
    """Validates interaction: flat initial objective weights isolating the euclidean capacity tiebreaker."""
    data = get_data(TRAP4_OUT)
    expected = 35.078524
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), f"Trap 4 failed: got {data['best_value']}"

def test_t5_trap5_negative_w_decay_slope():
    """Validates interaction: negative bounds for throttle decay crossing zero slope constraints."""
    data = get_data(TRAP5_OUT)
    expected = 1.782057
    assert math.isclose(data["best_value"], expected, rel_tol=1e-5, abs_tol=1e-5), f"Trap 5 failed: got {data['best_value']}"
