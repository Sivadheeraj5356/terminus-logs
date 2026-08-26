# Hex grid wave emit notes

Supported driver: `/app/environment/drv/run_td.sh`. That script walks pack
directories under `data/m9` and `data/z2` and writes one JSON object to
`/app/output/feasibility_cert.json`.

## Top-level members

The emit object carries `rows` plus `seal_hex`.

`rows` is the flat list of schedule rows across every pack directory.

`seal_hex` is the lowercase sha256 hex digest over the packed rows. The hex
string length is 64.

Each row carries these members.

`map_id` comes from that directory `meta.json`.

`wave_index` is the integer pulse index taken from the bag item.

`spawn_hex` is the chosen source node id for that pulse.

`pressure_score` is the finite per-pulse contribution after soft-floor
attenuation along the chosen path.

`leftover_budget` is the hard budget remaining after that map's admitted pulse
costs; specifically `max_cost` reduced by the summed pulse costs for the map.
Every row for one map carries the same leftover value.

`leak_margin` is `egress_cap` reduced by residual amplitude at the egress node
for that pulse. Values above zero mean the pulse does not breach the egress cap.

## Bag and meta shapes

Pack bags live in `bag.json`. Each bag has a `graph` object and an `items`
list.

Graph entries use node-id keys. Each node object carries role tag `t` with
value `S` for source, `M` for mid, or `X` for egress; list `e` of neighbor ids;
and optional float `k` attenuation weight on mid nodes.

Items are pulse objects with integer `i`, float `a` amplitude, integer `c`
cost, and list `s` of allowed source node ids.

Key order inside a bag object is not significant. Metadata in `meta.json`
carries `map_id` and integer `seed`.

## Limits and soft floors

Hard limits come from `pol/cap.toml`.

`max_cost` is the budget ceiling for summed pulse costs on one map.

`min_leftover` is the floor leftover_budget must meet or exceed.

`max_amp` refuses any pulse amplitude above this property.

`salt_hex` holds the even-length hex salt bytes fed into `seal_hex`.

Soft floors come from `pol/q_floor.json`.

`soft_floor` is the base attenuation scale for mid-node `k`.

`egress_cap` requires residual amplitude at an `X` node to stay strictly below
this property after attenuation.

`digits` is how many decimals to keep on float fields in emits and seal packing.

## Path residual and pressure

Canonical bag assembly sorts graph node ids lexicographically, sorts each node's
neighbor list `e` lexicographically, and sorts items by ascending `i`. For a
chosen source, the path is the unique shortest walk to the nearest `X` node over
undirected edges in `e` using classic BFS. Neighbor discovery order is the
presentation order of each node's `e` list, then reverse edges in graph-key
presentation order. After canonical assembly that order is lex-stable.
Equal-length walks keep the first-discovered egress walk under that expansion
order.

Along that path, each mid node with weight `k` multiplies residual amplitude by
soft_floor times the greater of 0.05 and one minus k. Starting residual is the
pulse amplitude `a`.

Then leak_margin is egress_cap reduced by residual at egress. Admit a pulse only
when leak_margin is strictly positive and amplitude `a` is at most max_amp.
pressure_score for an admitted pulse is residual amplitude after all mid-node
attenuations (the residual that arrives at egress), rounded to digits.

For one map, choose a subset of pulses (each with one allowed source from `s`)
that maximizes the sum of per-pulse pressure_score values while keeping summed
costs at or under max_cost reduced by min_leftover. When several subsets tie on
total pressure, prefer the subset whose sorted wave_index then spawn_hex pairs
are lexicographically smaller. When one pulse has several valid sources for the
same subset choice, prefer the lexicographically smaller spawn_hex.

## Seal packing

Build seal_hex as sha256 hex of the salt bytes from salt_hex, then a newline,
then one line per row sorted by map_id, then wave_index, then spawn_hex. Join
row fields with `|` in this order:
map_id, wave_index, spawn_hex, pressure_score, leftover_budget, leak_margin.
Floats use exactly digits decimals.

Library behavior under `gp/` and `hz/` must stay consistent with this emit path.
CLI glue alone is not enough if imported call sites diverge.
