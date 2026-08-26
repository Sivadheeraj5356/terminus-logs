The release security team needs an offline keyring cutover gate for one verifier image. The staged inputs describe candidate trust bundles, issuer limits, revoked issuers, and the claims that must be preserved during the cutover.

Write `/app/keyring_cutover_gate.go`, build `/app/keyring_cutover_gate`, and run it as `/app/keyring_cutover_gate /app/input_data/request.json /app/input_data/catalog.json /app/output_data/cutover_plan.json` without modifying the inputs.

Use `/app/keyring_cutover_contract.md` as the schema contract for `request.json`, `catalog.json`, and `cutover_plan.json`. The verifier checks exact JSON structure and key order, so follow that contract precisely.

Two output details matter exactly:

- `selected_bundle_ids` is the canonical activation order, not an unordered set and not a separately sorted list.
- `summary.missing_claims` is an array of claim-name strings from `request.required_claims` that are still below minimum strength after the cutover, in `request.required_claims` order.

Core decision rules:

- Only usable bundles may be selected: `runtime` must match `request.target_runtime`, `track` must be in `request.allowed_tracks`, and `issuer` must not be in `request.revoked_issuers`.
- Evaluate validity on the final selected set, not one bundle at a time.
- In the final set, enforce bundle-id uniqueness, family uniqueness, slot uniqueness for non-null slots, total `footprint_kb` within `request.max_total_footprint_kb`, and issuer counts within `request.issuer_caps`.
- Every selected bundle prerequisite must be satisfied by the final maximum claim strengths from the selected bundles plus `baseline_claims`.
- Every exclude token is checked against every other selected bundle. A token matches either the other bundle `family` or any claim name in the other bundle `claims`.
- Claim satisfaction uses maximum strength per claim name. `baseline_claims` participate in prerequisite checks, required-claim checks, and activation ordering, but never appear in `selected_bundle_ids`.

Canonical activation order:

- Repeatedly emit the lexicographically smallest remaining selected bundle id whose prerequisites are already satisfied by `baseline_claims` plus the claims from earlier emitted bundles.
- If a selected set cannot be fully emitted by that rule, it is invalid.

Choose the globally best valid plan with these tie-breaks, in order:

1. Maximize the number of satisfied rows in `request.required_claims`.
2. Minimize total selected `risk`.
3. Minimize total selected `footprint_kb`.
4. Minimize the number of selected bundles.
5. If still tied, compare the full `selected_bundle_ids` arrays lexicographically and choose the smaller one; if one is a strict prefix of the other, the shorter array is smaller.

Hidden variants can include roughly 40 to 50 usable bundles, duplicate required claim rows, non-null and null slots, multiple bundle ids that share a family, and optional branches that compete on issuer caps, footprint budget, excludes, and tie-breaks. A naive subset enumeration is not expected to finish within the verifier timeout.

If the best valid cutover still leaves required claims unsatisfied, write `status: "gap"` and still write the full output object. In that case `selected_bundle_ids` must still be a JSON array and is `[]` when no bundles are selected.
