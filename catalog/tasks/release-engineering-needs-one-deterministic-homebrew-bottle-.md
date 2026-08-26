# Release engineering needs one deterministic Homebrew bottle promotion plan from 

Submission: `f36b77cc-eda3-4e55-94d5-b5fc767fb10e`  
Slug: `release-engineering-needs-one-deterministic-homebrew-bottle-`  
Latest archive: `f36b77cc-eda3-4e55-94d5-b5fc767fb10e_submission_2026-07-16T09_48_47.827Z.zip`  
Revisions in Dropbox: 6

## Task summary

Release engineering needs one deterministic Homebrew bottle promotion plan from the offline fixture at `/srv/bottleplan`. Implement the planner in `/opt/bottleplan/app` so `./bin/bottleplan plan --catalog-root <abs-path> --request <abs-path> --out <abs-path>` selects one globally consistent formula version per formula, one bottle per requested platform, and writes promotion artifacts without modifying `/srv/bottleplan/catalog` or `/srv/bottleplan/requests`. Inputs: - Use only `/srv/bottleplan/catalog/formula_catalog.json`, `/srv/bottleplan/catalog/platform_policy.json`, `/srv/bottleplan/catalog/mirror_inventory.json`, and the JSON file passed as `--request`. - The request has `request_id`, ordered `target_platforms`, ordered `root_formulae`, `allow_prerelease`, `max_new_digests`, `max_new_bytes`, and `relocation_policy` (`strict` or `allow_cellar_specific`). Root rows have `name`, `version_range`, lowercase `required_features`, and `allow_keg_only`. - Catalog formula versions have `version`, `revision`, `prerelease`, `keg_only`, ordered `dependencies`, and `bottles`. Dependency edges have `name`, `version_range`, and `requires_features`; an edge is active only when every required feature is present for that instance. Bottles have `platform`, `digest`, `bytes`, `cellar`, `rebuild`, `relocatable`, `codesigned`, and `runtime_floor`. - Platform policy rows have `platform`, `runtime_kind`, `minimum_runtime`, and `require_codesigned`; mirror inventory has `mirrored_digests`.

Required artifacts include: not named as `/app` paths.

Author Anonymous tagged this **hard** build-and-dependency-management task (go, homebrew, bottle-promotion, offline-cli, deterministic-output, dependency-planning).

Time estimates: expert ~270 min, junior ~540 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `f36b77cc-eda3-4e55-94d5-b5fc767fb10e_submission_2026-07-16T09_48_47.827Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
