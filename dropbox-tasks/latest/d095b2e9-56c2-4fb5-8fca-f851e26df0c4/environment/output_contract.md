# JSON certificate

The final MiniZinc JSON object must expose these integer fields with exact nesting:

- `select`: `[residue][rotamer]`, binary.
- `bridge`: `[bridge]`, binary.
- `class_count`: `[class]`, integer.
- `state_energy`: `[state]`, integer.
- `mutation_count`, `mutation_cost`, `exposure_cost`, `top_two_energy`,
  `secondary_cost`, and `total_cost`: scalar integers.

The reported audits must equal values recomputed from `select` and `bridge`,
and MiniZinc's `_objective` must equal `total_cost`.
