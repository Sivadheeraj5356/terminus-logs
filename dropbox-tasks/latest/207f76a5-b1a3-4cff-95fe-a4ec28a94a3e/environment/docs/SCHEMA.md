# Input schema

Your program is invoked as `Rscript /app/join_count.R <dir>`, where `<dir>` is a
directory containing exactly two comma-separated files, `units.csv` and
`edges.csv`. An example instance is provided at `/app/data`.

## units.csv

The first line is the exact header `unit_id,label,value`. Each following line is
one areal unit as `unit_id,label,value`:

- `unit_id` is a non-empty string identifier (arbitrary tokens; do not assume
  they are integers or contiguous). Identifiers are unique across the file.
- `label` is the binary categorical attribute, exactly `0` (white) or `1`
  (black).
- `value` is the numeric attribute: an integer (an optional leading `-` then one
  or more digits). It is the variable analysed by Moran's I and Geary's C.

There is at least one unit. Let `n` be the number of units, `n1` the number of
units with `label = 1`, and `n0 = n - n1`.

## edges.csv

The first line is the exact header `unit_i,unit_j`. Each following line is one
undirected binary contiguity edge as `unit_i,unit_j`, where both fields are
identifiers that appear in `units.csv`.

- Edges are undirected: the pair `{unit_i, unit_j}` is unordered.
- No self-edges: `unit_i` and `unit_j` must differ.
- No repeats: an unordered pair appears at most once. Listing both `a,b` and
  `b,a` is a repeat.

There may be zero edges. The edge set defines the first-order symmetric binary
weight matrix `W1` with `w_ij = w_ji = 1` when `{i, j}` is an edge and `0`
otherwise, and zero diagonal. A second-order weight matrix `W2` and a
row-standardized weight matrix are then derived from `W1`; their exact
construction and the full statistic suite are specified in `OUTPUT-CONTRACT.md`.

## Malformed input

Any deviation from the above (a wrong or missing header, a missing file, an
empty identifier, a `label` other than `0`/`1`, a `value` that is not an integer,
a row without exactly the required number of comma-separated fields, a duplicate
`unit_id`, an edge referencing an unknown identifier, a self-edge, or a repeated
edge) is malformed. On any malformed input the program prints exactly one line,
`ERROR`, and nothing else.
