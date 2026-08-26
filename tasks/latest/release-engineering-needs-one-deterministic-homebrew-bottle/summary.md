# Release engineering needs one deterministic Homebrew bottle promotion plan from

- **UUID:** `f36b77cc-eda3-4e55-94d5-b5fc767fb10e`
- **Slug:** `release-engineering-needs-one-deterministic-homebrew-bottle`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Release engineering needs one deterministic Homebrew bottle promotion plan from the offline fixture at `/srv/bottleplan`. Implement the planner in `/opt/bottleplan/app` so `./bin/bottleplan plan --catalog-root <abs-path> --request <abs-path> --out <abs-path>` selects one globally consistent formula version per formula, one bottle per requested platform, and writes promotion artifacts without modifying `/srv/bottleplan/catalog` or `/srv/bottleplan/requests`.

Inputs: - Use only `/srv/bottleplan/catalog/formula_catalog.json`, `/srv/bottleplan/catalog/platform_policy.json`, `/srv/bottleplan/catalog/mirror_inventory.json`, and the JSON file passed as `--request`. - The request has `request_id`, ordered `target_platforms`, ordered `root_formulae`, `allow_prerelease`, `max_new_digests`, `max_new_bytes`, and `relocation_policy` (`strict` or `allow_cellar_specific`).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
