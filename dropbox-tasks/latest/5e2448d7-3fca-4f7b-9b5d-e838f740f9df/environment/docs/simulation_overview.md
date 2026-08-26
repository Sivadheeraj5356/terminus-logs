# Simulation overview

The brine driver replays wind tapes against lane geometry.
Some pond packs ship a mid-tape `resume_state.json` beside the plan when a run is continued from a prior shift.
Sector routing may memoize recent octant resolutions under the output directory between invocations.

Daily survey vertices are emitted in the same arm packing order as the top-level `arms` array. When comparing packs, match vertices by `arm_key` as well as by position.
