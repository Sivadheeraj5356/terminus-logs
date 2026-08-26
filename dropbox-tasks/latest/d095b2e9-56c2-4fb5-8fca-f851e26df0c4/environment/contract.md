# Normative contract

`select[r,k]` is binary and selects exactly one rotamer at each residue. A
selected rotamer must have `valid[r,k]=1`. `class_count[c]` is the exact
number of selected rotamers whose `aa_class` is `c`, and must lie between
`class_min[c]` and `class_max[c]`. The sum of selected `charge` values
must lie in the inclusive interval `[charge_min,charge_max]`.
`mutation_count` counts residues whose selected rotamer differs from
`native_rotamer[r]` and may not exceed `mutation_budget`.

For every residue pair `r<q`, the selected rotamer pair is forbidden when
`clash[r,k,q,l]=1`. Every bridge candidate has two distinct endpoints. A
bridge candidate may be selected only when the selected rotamers at both
`bridge_left[b]` and `bridge_right[b]` are bridge capable.
Exactly `required_bridges` candidates are selected, and each residue may be
an endpoint of at most one selected bridge.

For state `s`, `state_energy[s]` is the sum of selected unary energies,
plus `pair_energy[s,r,k,q,l]` for every contact with `r<q` and both
rotamers selected, minus `bridge_credit[s,b]` for every selected bridge.
For each non-target state `s`, enforce
`state_energy[target_state] + stability_margin[s] <= state_energy[s]`.

`mutation_cost` and `exposure_cost` are the sums of the corresponding
selected penalties. `top_two_energy` is the sum of the two largest state
energies; there are always at least two states. Define
`secondary_cost = sum(state_energy) + mutation_weight*mutation_cost +
exposure_weight*exposure_cost` and
`total_cost = robust_weight*top_two_energy + secondary_cost`. Instances
guarantee that all state energies and cost audits are nonnegative and that
`robust_weight` exceeds every possible secondary-cost difference, so the
objective first minimizes the top-two energy and then the secondary cost.
Minimize `total_cost`.
