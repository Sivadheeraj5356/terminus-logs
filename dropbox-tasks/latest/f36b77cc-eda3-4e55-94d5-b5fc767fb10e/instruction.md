Release engineering needs one deterministic Homebrew bottle promotion plan from the offline fixture at `/srv/bottleplan`. Implement the planner in `/opt/bottleplan/app` so `./bin/bottleplan plan --catalog-root <abs-path> --request <abs-path> --out <abs-path>` selects one globally consistent formula version per formula, one bottle per requested platform, and writes promotion artifacts without modifying `/srv/bottleplan/catalog` or `/srv/bottleplan/requests`.

Inputs:
- Use only `/srv/bottleplan/catalog/formula_catalog.json`, `/srv/bottleplan/catalog/platform_policy.json`, `/srv/bottleplan/catalog/mirror_inventory.json`, and the JSON file passed as `--request`.
- The request has `request_id`, ordered `target_platforms`, ordered `root_formulae`, `allow_prerelease`, `max_new_digests`, `max_new_bytes`, and `relocation_policy` (`strict` or `allow_cellar_specific`). Root rows have `name`, `version_range`, lowercase `required_features`, and `allow_keg_only`.
- Catalog formula versions have `version`, `revision`, `prerelease`, `keg_only`, ordered `dependencies`, and `bottles`. Dependency edges have `name`, `version_range`, and `requires_features`; an edge is active only when every required feature is present for that instance. Bottles have `platform`, `digest`, `bytes`, `cellar`, `rebuild`, `relocatable`, `codesigned`, and `runtime_floor`.
- Platform policy rows have `platform`, `runtime_kind`, `minimum_runtime`, and `require_codesigned`; mirror inventory has `mirrored_digests`.

Selection contract:
- Resolve every root and active dependency through the same globally selected version for each formula name.
- Root formulae are processed in request order; dependency traversal is preorder using selected-version dependency order.
- Candidate versions sort by semantic version descending, then revision ascending.
- A version is locally usable only inside the instance `version_range`.
- `keg_only` blocks only root requests whose `allow_keg_only` is false; dependency instances do not reject solely because a version is `keg_only`.
- Root `required_features` are deduplicated and sorted lexically before use. Dependency instances have no active features of their own; a dependency edge is followed only if its `requires_features` are all present in the parent instance. In `promotion_plan.json`, `active_features` is the sorted root `required_features` for root formulae and `[]` for non-root formulae. A selected formula's `dependencies` list includes only dependency edges whose `requires_features` are satisfied by that selected formula row's `active_features`, in catalog dependency order.
- `max_new_digests` counts unique selected bottle digests absent from `mirror_inventory.json`; `max_new_bytes` sums bytes for those unique new digests only.
- Rank complete feasible plans by fewer new digests, lower new bytes, lower total selected bottle rebuild sum, newer selected root versions in root request order, then lexicographically smaller sorted identities of `formula/<name>/<version>/<platform>@<digest>`.

Candidate report reasons are local to the candidate and ordered exactly as follows. First check `version_out_of_range`, `prerelease_blocked`, and `keg_only_blocked`; if any of those three reasons apply, emit exactly those reasons in order and do not evaluate bottle/platform reasons for that candidate. If none of those three reasons apply, evaluate every requested platform and accumulate all applicable bottle/platform reasons in the listed order. Do not stop after the first bottle/platform reason: a candidate can report both `runtime_floor_conflict` and `relocation_conflict`, for example. A missing platform contributes `platform_unavailable`; platforms that do have bottles are still checked for runtime floor, relocation, and codesigning.

| reason | condition |
|---|---|
| `version_out_of_range` | version misses the instance range |
| `prerelease_blocked` | version is prerelease and `allow_prerelease` is false |
| `keg_only_blocked` | root instance disallows keg-only and version is keg-only |
| `platform_unavailable` | any requested platform has no bottle |
| `runtime_floor_conflict` | any present bottle `runtime_floor` exceeds that platform `minimum_runtime` |
| `relocation_conflict` | policy is `strict` and any present bottle is not relocatable |
| `codesign_missing` | a codesign-required platform has an unsigned present bottle |

Dependency infeasibility, budget losses, and final ranking losses add no reasons; those candidates stay `eligible_not_chosen`.

Outputs:
- A successful run fully replaces stale contents under `--out` and writes exactly UTF-8 `promotion_plan.json`, `mirror_fetch.tsv`, and `candidate_report.json`.
- Bad subcommand, wrong flag order, missing arguments, or non-absolute `--catalog-root`, `--request`, or `--out` must exit nonzero, write no outputs, and print exactly `usage: bottleplan plan --catalog-root <abs-path> --request <abs-path> --out <abs-path>` to stderr.
- If no feasible plan exists, exit nonzero, leave no partial outputs, and print exactly `bottleplan: no feasible promotion plan` to stderr.
- Repeated runs over identical inputs must be byte-identical. JSON files are compact JSON with one trailing newline.

`promotion_plan.json` key order is `request_id`, `relocation_policy`, `target_platforms`, `root_selections`, `selected_formulae`, `unique_new_digest_count`, `total_new_bytes`, `total_rebuild_sum`. `root_selections` follows request order and has `name`, `selected_version`. `selected_formulae` sorts by formula name and has `name`, `version`, `revision`, lexical `active_features`, `root_requested`, dependency-order `dependencies`, and `bottles`. Each dependency row is the complete active edge object with key order `name`, `version_range`, `requires_features`; do not reduce dependencies to names. Bottle rows follow `target_platforms` order and have `platform`, `digest`, `cached`, `bytes`, `rebuild`, `relocatable`, `codesigned`, `runtime_floor`.

`mirror_fetch.tsv` header is exactly `step	action	digest	formula_name	platform	bytes	cached	used_by_formulae`. It has one row per unique selected digest. `action` is `fetch` unless the digest is mirrored, in which case it is `reuse_mirrored`; `cached` is `true` or `false`. `used_by_formulae` is the comma-separated sorted list of `<formula>@<platform>` users. For shared digests, `formula_name` and `platform` come from the lexicographically smallest user. Rows sort with `fetch` before `reuse_mirrored`, then `formula_name`, `platform`, `digest`; `step` is 1-based after sorting.

`candidate_report.json` key order is `request_id`, `selected_versions`, `instances`. `selected_versions` sorts by formula name and has `name`, `version`. `instances` follows preorder traversal over the selected dependency tree and has `instance_ref`, `parent_instance_ref`, `name`, `version_range`, lexical `required_features`, and `candidate_versions`. Root refs are `root.<name>` with `parent_instance_ref = NONE`; dependency refs are `<parent_instance_ref>-><dependency_name>`. Candidate rows sort by semantic version descending, then revision ascending, and have `version`, `revision`, `status`, `reasons`; `status` is `selected`, `eligible_not_chosen`, or `rejected_gate`.

The planner must work for copied scenario roots and other valid inputs with the same schema, not only the visible fixture.
