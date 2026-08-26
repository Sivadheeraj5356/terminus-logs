Topology schema version 4.

Top-level keys: schema_version, gravity_m_s2, nodes, links, initial_inflows.

gravity_m_s2 is finite and positive. Node and link IDs match ^[a-z][a-z0-9_-]{0,63}$ and are unique. Array order is not semantic; normalize by sorting nodes and links by ID for digests.

Storage nodes require node_type storage, initial_level_m inside a strictly increasing level/volume curve of at least two knots, and a positive storage_curve_revision.

Boundary nodes require node_type boundary and a finite initial_level_m. They have no stored volume.

Links connect two distinct existing nodes and must not connect two boundaries. Positive flow is from from_node to to_node.

Link types:
- gate: discharge_coefficient, area_m2, initial_control in [0,1], maximum_abs_flow_m3_s
- weir: discharge_coefficient, width_m, crest_level_m, initial_control in [0,1], maximum_abs_flow_m3_s
- pump: initial_control in [0, maximum_abs_flow_m3_s], maximum_abs_flow_m3_s

initial_inflows list storage-node flows (finite, may be negative). Omitted storage nodes start at zero inflow.
