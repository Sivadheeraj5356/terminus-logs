`request.json`

- top-level object
- `generated_at`: string
- `rollout_id`: string
- `target_runtime`: string
- `allowed_tracks`: string array
- `revoked_issuers`: string array
- `max_total_footprint_kb`: integer
- `issuer_caps`: object whose values are integers
- `baseline_claims`: array of objects with `name` string and `strength` integer
- `required_claims`: array of objects with `name` string and `min_strength` integer

`catalog.json`

- top-level object
- `bundles`: array of objects
- each bundle has:
  - `id`: string
  - `family`: string
  - `version`: string
  - `runtime`: string
  - `track`: string
  - `issuer`: string
  - `footprint_kb`: integer
  - `risk`: integer
  - `slot`: string or null
  - `claims`: array of objects with `name` string and `strength` integer
  - `prerequisites`: array of objects with `name` string and `min_strength` integer
  - `excludes`: string array

`cutover_plan.json`

- top-level object with keys in this exact order:
  1. `generated_at`
  2. `status`
  3. `selected_bundle_ids`
  4. `summary`
- `status` is exactly `ready` or `gap`
- string comparisons are exact and case-sensitive
- `selected_bundle_ids` is a JSON array of bundle-id strings in canonical activation order and never `null`
- canonical activation order means the same repeated rule described in `instruction.md`: repeatedly emit the lexicographically smallest remaining selected bundle id whose prerequisites are already satisfied by `baseline_claims` plus the claims from earlier emitted bundle ids
- the output file must still be written for `gap` cases and for `selected_bundle_ids: []`
- `summary` is an object with keys in this exact order:
  1. `total_footprint_kb`
  2. `total_risk`
  3. `claim_strengths`
  4. `missing_claims`
- `claim_strengths` is a JSON array in `request.required_claims` order
- duplicate `required_claims` names still produce separate `claim_strengths` rows and separate `missing_claims` entries when applicable
- each `claim_strengths` row contains only `name` and `strength`, in that order
- `missing_claims` is a JSON array of claim-name strings in `request.required_claims` order and never `null`
- each `missing_claims` entry is exactly the `name` string from one unsatisfied `request.required_claims` row; do not emit objects in `missing_claims`
