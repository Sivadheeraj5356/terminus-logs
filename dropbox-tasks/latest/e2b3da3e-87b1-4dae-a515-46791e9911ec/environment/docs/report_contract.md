Transient report schema version 4.

Top-level key order: schema_version, case_id, case_digest_hex, completed, simulated_until_s, samples, diagnostics, audit_digest_hex.

Sample keys: time_s, nodes, links, conservation.
Storage node sample: node_id, node_type, curve_revision, level_m, volume_m3.
Boundary node sample: node_id, node_type, level_m.
Link sample: link_id, link_type, flow_m3_s, control.
Conservation sample: current_total_storage_m3, cumulative_external_volume_m3, mass_residual_m3.

Nodes ordered by node_id ascending; links by link_id ascending.

Diagnostics: accepted_substeps, rejected_attempts, newton_iterations, minimum_accepted_step_s, maximum_accepted_step_s, maximum_abs_mass_residual_m3.

Rounding (round-half-even): level/volume/flow/cumulative_external 9 places; mass_residual 12 places; step-size diagnostics 9 places. Do not round internals.

audit_digest_hex is the lowercase SHA-256 hex of the report body exactly as serialized to disk, with the trailing `,"audit_digest_hex":"..."` field removed and a final `}` restored. Do not re-parse, re-sort keys, reformat numbers, or otherwise renormalize the JSON before hashing. Top-level fields appear in the fixed order above; nested objects use the field orders shown in this contract. The written file ends with one newline after the complete object (the newline is not part of the hash material).

Writes are atomic via sibling temporary files and rename. With snapshot output, report and snapshot form one logical commit.
