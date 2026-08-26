# Conan staged dependency and artifact plan

The command reads four JSON files from the input directory: `profile-requests.json`, `recipe-index.json`, `conan-lock.json`, and `package-cache.json`. These files intentionally overlap. The request file lists ordered build stages, the index lists available versions and transitive requirements, the lock file lists versions already committed by an earlier run, and the cache lists reusable build artifacts. No one file is authoritative by itself.

This task models Conan recipe/version selection under a fixed profile. The JSON field named `features` represents Conan options that participate in the package ID, and `toolchain` represents the profile lane. Once a recipe version is committed by the lock file or an earlier stage, later option growth changes the binary package ID but not the recipe version.

All versions use three integer components. Constraints are comma-separated comparisons using `>=`, `>`, `<=`, `<`, or `=`. A candidate version is usable only when it satisfies every accumulated constraint for that package and lists the requested toolchain.

The `Conan` model is:

- The request file has `toolchain` and `stages`. Stages are processed in array order. Each stage has an `id` and `requests`.
- A request has `target`, `constraint`, and `features`. `features` may be empty and must still be treated as an empty array.
- A repository package has `name` and `versions`. Each version has `version`, `dependencies`, `default_features`, `supported_features`, `feature_dependencies`, `toolchains`, and `artifacts`.
- A dependency object has `target`, `constraint`, and `features`.
- The lock file has `locked`; each locked entry has `name`, `version`, `features`, and `reason`.
- The cache file has `entries`; each entry has `name`, `version`, `toolchain`, `features`, and `hash`.

State rules:

- Locked entries from `conan-lock.json` are already committed before the first stage. Their version may not change. They must appear in `final_lock`.
- Locked entries become active with their recipe `default_features` before stage processing begins, even if no later request touches that package.
- When a package is first selected during these stages, that version is committed permanently for later stages.
- Later stages may add features to an already selected package. Features are additive and never removed.
- A selected package's active feature set is the union of its default features, locked features, requested features, and feature dependencies activated so far. Output feature arrays are sorted lexicographically.
- If an active feature has dependencies in `feature_dependencies`, those dependencies are additive. Activating a feature does not short-circuit normal dependencies.
- If a selected or locked version does not satisfy a newly accumulated constraint, emit one conflict for that package in that stage with reason `locked-version`. Continue processing other packages.
- If a selected or locked version lacks a requested feature, emit one conflict for that package in that stage with reason `unsupported-feature`. Continue processing other packages.
- If no selectable version exists for an unselected package, emit one conflict for that package in that stage with reason `no-candidate`.

Selection and artifact rules:

- For an unselected package, use only repository candidates that satisfy all accumulated constraints, the current toolchain, and any direct requests for the same package that appear in later stages.
- If several candidates remain, choose the one whose final requested feature set has a reusable artifact in `package-cache.json`. If still tied, choose the candidate with fewer direct dependencies after requested feature dependencies are included. If still tied, choose the highest version. If still tied, compare the package name and then the version string lexicographically.
- A cache entry is reusable only when `name`, `version`, `toolchain`, sorted `features`, and `hash` exactly match one artifact declared by the selected repository version for the same sorted feature set. Supersets and subsets are not reusable.
- A stage emits an action only for a package newly selected in that stage or whose active feature set grew in that stage. Already active packages that did not change appear only in `final_lock`.
- For each changed package, put it in `reused` if the exact cache rule matches; otherwise put it in `built`.

Output:

Write a JSON object to the requested output path. The verifier compares parsed JSON values. Use these fields:

- `stages`: array in input stage order. Each stage object has `id`, `selected`, `reused`, `built`, and `conflicts`.
- `selected`, `reused`, and `built` contain objects with `name`, `version`, and `features`. Sort each array by `name`.
- `conflicts` contains objects with `name` and `reason`. Sort conflicts by `name`, then `reason`.
- `final_lock`: all committed packages, including prior locked packages, sorted by `name`, with `name`, `version`, and `features`.
- `summary`: object with integer fields `selected`, `reused`, `built`, and `conflicts`.

Use empty arrays instead of `null`. Unknown JSON fields should be ignored. The command must not modify the input files.
