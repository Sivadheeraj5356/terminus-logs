Forcing is UTF-8 JSONL. Nonempty lines only; file ends with newline. Empty lines are rejected. Event IDs and source sequences are unique. Physical line order is not semantic.

Common keys: event_id, source_seq, time_s, event_type.

Canonical order: (time_s, event_type_rank, source_seq, event_id) with ranks
storage_curve_revision=0, boundary_stage=1, link_control=2, external_inflow=3, volume_impulse=4.

At a boundary time: apply events in canonical order, then emit the sample if required, then integrate onward. Events at start_time_s apply before the first sample. Events at stop/end apply before the final sample.

Event payloads:
- storage_curve_revision: node_id, revision (= active+1), storage_curve; conserve volume; recompute level
- boundary_stage: node_id, level_m
- link_control: link_id, control (gate/weir [0,1]; pump [0, max])
- external_inflow: node_id, flow_m3_s (replaces previous)
- volume_impulse: node_id, delta_volume_m3 (adds to cumulative external volume)
