# Geometry manifest and shared splits

geometry_manifest.json declares schema_version gaa-geometry-v1, reference_temp_c, and a geometries array. Each geometry row contains geometry_id, L_nm, W_nm, nfin, and split_group.

Geometries sharing the same split_group are fit with one shared parameter set. Effective width is W_nm times nfin in meters. Effective length is L_nm in meters. Tapeout lists geometries sorted by geometry_id ascending and serializes length and width under lowercase keys l_nm and w_nm.

Each distinct split_group is fitted independently. Before fitting a group, initialize all nine parameters from parameter_bounds.toml initial values rather than copying fitted values from another split_group. Process split groups in ascending split_group name order. Group B geometries use independent fit groups when split_group differs from A.
