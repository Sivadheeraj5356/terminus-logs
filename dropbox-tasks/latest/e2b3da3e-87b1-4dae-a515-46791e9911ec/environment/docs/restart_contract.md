Restart snapshot schema version 4.

Top-level keys: schema_version, case_digest_hex, forcing_cursor, simulated_until_s, storage_state, boundary_levels, link_controls, external_inflows, active_curves, prior_samples, solver_state, conservation_state, snapshot_digest_hex.

forcing_cursor: processed_bytes (complete JSONL line boundary), prefix_sha256 of those bytes, maximum_source_seq.

storage_state / boundary_levels / link_controls / external_inflows / active_curves are sorted by ID.

solver_state: next_step_s, accepted_substeps, rejected_attempts, newton_iterations, minimum_accepted_step_s, maximum_accepted_step_s, maximum_abs_mass_residual_m3.

conservation_state: initial_total_storage_m3, cumulative_external_volume_m3.

prior_samples: exact semantic samples through the snapshot time.

snapshot_digest_hex is the lowercase SHA-256 hex of the snapshot body exactly as serialized to disk, with the trailing `,"snapshot_digest_hex":"..."` field removed and a final `}` restored. Do not re-parse, sort keys, reformat numbers, or otherwise renormalize before hashing. Top-level fields appear in the fixed order listed above (not lexicographic key order). Arrays that the contract requires sorted by ID are already sorted in that serialized body. The written file ends with one newline after the complete object (the newline is not part of the hash material).

Restore requires matching case digest, forcing prefix hash and size, appended events with source_seq > stored max and time_s > simulated_until_s. Reject rewritten prefixes, truncations, and reused sequences without mutating existing outputs.
