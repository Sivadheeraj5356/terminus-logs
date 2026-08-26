Evaluate link flows from active controls and midpoint node levels. Positive flow is from from_node to to_node. Apply maximum_abs_flow_m3_s after the raw law.

Gate:
delta_h = h_from - h_to
K = control * discharge_coefficient * area_m2
q = K * sign(delta_h) * sqrt(2 * gravity * abs(delta_h))
Zero when delta_h == 0. Bidirectional.

Weir:
upstream_head = h_from - crest_level
Zero when upstream_head is not positive.
submergence_ratio = clamp((h_to - crest_level) / upstream_head, 0, 1)
submergence_factor = (1 - submergence_ratio) ^ 0.385
q = control * discharge_coefficient * width_m * upstream_head^1.5 * submergence_factor
Never negative.

Pump:
q = control, then capped by maximum_abs_flow_m3_s.
