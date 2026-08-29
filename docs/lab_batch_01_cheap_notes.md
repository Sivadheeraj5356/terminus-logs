# Batch 01 — cheap-protocol notes

**Updated:** 2026-08-29T01:45:06Z
**Protocol:** terminus-2, `-k 5`, Haiku + second cheap arm. Frontier 8-run history is separate.
**Stump:** `valid_fail / (solved + valid_fail)`. Infra and timeout excluded.

| Task | Oracle | Agent n | Solved | Valid fail | Infra | Timeout | Stump |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `repair-the-pendulum-motion-solver` | yes | 25 | 9 | 14 | 2 | 0 | 60.9 |
| `hypersonic-fragment-cascade-epoch-atlas` | yes | 17 | 10 | 7 | 0 | 0 | 41.2 |
| `the-dyeworks-tool-is-a-command-line-reader-at-app-environmen` | yes | 11 | 3 | 4 | 4 | 0 | 57.1 |
| `the-root-ca-that-signed-our-east-west-mtls-credentials-is-co` | yes | 2 | 1 | 1 | 0 | 0 | 50.0 |
| `apexora-global-wave-3-campus-segmentation-is-blocked-across` | yes | 2 | 1 | 1 | 0 | 0 | 50.0 |
| `i-need-the-offline-binary-cache-closure-planner-in-app-task` | yes | 2 | 1 | 1 | 0 | 0 | 50.0 |
| `the-harborlane-replay-desk-needs-a-reusable-offline-planner` | yes | 2 | 1 | 1 | 0 | 0 | 50.0 |
| `we-re-putting-together-a-stratified-k-fold-evaluation-kit-un` | yes | 2 | 1 | 1 | 0 | 0 | 50.0 |
| `wildlife-counting-becomes-a-field-planning-game-when-uncerta` | yes | 2 | 1 | 0 | 0 | 1 | 0.0 |
| `booking-slot-merge` | yes | 2 | 1 | 1 | 0 | 0 | 50.0 |

## Themes (from traces + CTRF)

### `repair-the-pendulum-motion-solver`

- openai/gpt-5.6-sol: valid fail — test_outputs.py::test_frequency_within_tolerance, test_outputs.py::test_decay_within_tolerance, test_outputs.py::test_report_stdout_matches_snapshot
- anthropic/claude-opus-5: infra (BadRequestError)
- anthropic/claude-opus-5: solved
- anthropic/claude-opus-5: valid fail — test_outputs.py::test_graph_node_count_matches_edges
- anthropic/claude-opus-5: infra (RuntimeError)
- anthropic/claude-haiku-4-5: valid fail — test_outputs.py::test_frequency_within_tolerance, test_outputs.py::test_decay_within_tolerance, test_outputs.py::test_graph_node_count_matches_edges, test_outputs.py::test_report_stdout_matches_snapshot
- anthropic/claude-haiku-4-5: valid fail — test_outputs.py::test_populates_output_tables, test_outputs.py::test_jobs_marked_processed, test_outputs.py::test_frequency_within_tolerance, test_outputs.py::test_decay_within_tolerance
- openai/gpt-5.6-sol: solved
- Failing tests: `test_outputs.py::test_frequency_within_tolerance`, `test_outputs.py::test_decay_within_tolerance`, `test_outputs.py::test_report_stdout_matches_snapshot`, `test_outputs.py::test_graph_node_count_matches_edges`, `test_outputs.py::test_populates_output_tables`, `test_outputs.py::test_jobs_marked_processed`, `test_outputs.py::test_rejected_counts_match`, `test_outputs.py::test_graph_artifacts_emitted`

### `hypersonic-fragment-cascade-epoch-atlas`

- anthropic/claude-opus-5: solved
- anthropic/claude-opus-5: valid fail — tests/test_outputs.py::test_alpha_collision_occurs_and_matches_reference
- openai/gpt-5.6-sol: solved
- openai/gpt-5.6-sol: valid fail — tests/test_outputs.py::test_bravo_catalog_override_dir, tests/test_outputs.py::test_alpha_collision_occurs_and_matches_reference, tests/test_outputs.py::test_flare_absolute_density_scale_not_multiplicative, tests/test_outputs.py::test_hidden_chain_reaction_independent_of_bundled
- Failing tests: `test_export_sequence_monotonic_and_stable_hash`, `tests/test_outputs.py::test_alpha_collision_occurs_and_matches_reference`, `tests/test_outputs.py::test_bravo_catalog_override_dir`, `tests/test_outputs.py::test_flare_absolute_density_scale_not_multiplicative`, `tests/test_outputs.py::test_hidden_chain_reaction_independent_of_bundled`, `tests/test_outputs.py::test_ledger_epochs_match_reference_timestamps`

### `the-dyeworks-tool-is-a-command-line-reader-at-app-environmen`

- openai/gpt-5.6-sol: valid fail — test_outputs.py::test_valid_corpus_parses_cleanly, test_outputs.py::test_indirect_value_still_parses, test_outputs.py::test_deep_tree_still_parses, test_outputs.py::test_lot_ref_still_resolves
- openai/gpt-5.6-sol: infra (RuntimeError)
- anthropic/claude-opus-5: infra (BadRequestError)
- anthropic/claude-opus-5: solved
- anthropic/claude-opus-5: valid fail — test_outputs.py::test_exploit_alloc_rejected, test_outputs.py::test_generated_more_nodes_than_count_rejected
- Failing tests: `test_outputs.py::test_valid_corpus_parses_cleanly`, `test_outputs.py::test_indirect_value_still_parses`, `test_outputs.py::test_deep_tree_still_parses`, `test_outputs.py::test_lot_ref_still_resolves`, `test_outputs.py::test_boundary_valid_files_still_parse`, `test_outputs.py::test_generated_valid_parses`, `test_outputs.py::test_generated_depth_256_nesting_parses`, `test_outputs.py::test_generated_max_size_file_parses`

### `the-root-ca-that-signed-our-east-west-mtls-credentials-is-co`

- anthropic/claude-haiku-4-5: valid fail — test_outputs.py::test_schedule_is_the_exact_optimum, test_outputs.py::test_schedule_is_the_exact_optimum, test_outputs.py::test_schedule_is_the_exact_optimum
- Failing tests: `test_outputs.py::test_schedule_is_the_exact_optimum`

### `apexora-global-wave-3-campus-segmentation-is-blocked-across`

- anthropic/claude-haiku-4-5: valid fail — test_outputs.py::TestWave3Identity::test_schema_and_device_count, test_outputs.py::TestWave3Identity::test_evidence_export_invariants, test_outputs.py::TestWave3Identity::test_vlan_export_invariants, test_outputs.py::TestWave3Identity::test_all_vlan_checks_pass
- Failing tests: `test_outputs.py::TestWave3Identity::test_schema_and_device_count`, `test_outputs.py::TestWave3Identity::test_evidence_export_invariants`, `test_outputs.py::TestWave3Identity::test_vlan_export_invariants`, `test_outputs.py::TestWave3Identity::test_all_vlan_checks_pass`, `test_outputs.py::TestWave3Identity::test_vlan_catalog_count`, `test_outputs.py::TestWave3Identity::test_no_legacy_sources_consulted`, `test_outputs.py::TestWave3Identity::test_retired_vlan_families_from_precedence`, `test_outputs.py::TestWave3Identity::test_superseded_sections_empty`

### `i-need-the-offline-binary-cache-closure-planner-in-app-task`

- anthropic/claude-haiku-4-5: valid fail — test_public_and_visible_samples, test_generated_compatible_cases, test_copied_root_and_deterministic_rerun, test_builds_native_binary
- Failing tests: `test_public_and_visible_samples`, `test_generated_compatible_cases`, `test_copied_root_and_deterministic_rerun`, `test_builds_native_binary`

### `the-harborlane-replay-desk-needs-a-reusable-offline-planner`

- anthropic/claude-haiku-4-5: valid fail — test_public_root_is_solved_and_schema_is_canonical, test_generated_compatibility_matrix
- Failing tests: `test_public_root_is_solved_and_schema_is_canonical`, `test_generated_compatibility_matrix`

### `we-re-putting-together-a-stratified-k-fold-evaluation-kit-un`

- anthropic/claude-haiku-4-5: valid fail — test_outputs.py::TestFoldAssembler::test_stock_exit_zero, test_outputs.py::TestFoldAssembler::test_stock_ok_true, test_outputs.py::TestFoldAssembler::test_stock_row_count, test_outputs.py::TestFoldAssembler::test_stock_fold_count
- Failing tests: `test_outputs.py::TestFoldAssembler::test_stock_exit_zero`, `test_outputs.py::TestFoldAssembler::test_stock_ok_true`, `test_outputs.py::TestFoldAssembler::test_stock_row_count`, `test_outputs.py::TestFoldAssembler::test_stock_fold_count`, `test_outputs.py::TestFoldAssembler::test_stock_label_column`, `test_outputs.py::TestFoldAssembler::test_stock_staged_path_absolute`, `test_outputs.py::TestFoldAssembler::test_stock_staged_path_value`, `test_outputs.py::TestFoldAssembler::test_stock_staged_file_exists`

### `wildlife-counting-becomes-a-field-planning-game-when-uncerta`

- anthropic/claude-haiku-4-5: timeout (excluded from stump)
- Failing tests: `test_outputs.py::TestOutputs::test_census_case`

### `booking-slot-merge`

- anthropic/claude-haiku-4-5: valid fail — test_outputs.py::test_report_span_respects_epoch_fence, test_outputs.py::test_report_exact_layout, test_outputs.py::test_check_epoch_regression_across_files
- Failing tests: `test_outputs.py::test_report_span_respects_epoch_fence`, `test_outputs.py::test_report_exact_layout`, `test_outputs.py::test_check_epoch_regression_across_files`

