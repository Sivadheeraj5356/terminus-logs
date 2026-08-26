# Valuation policy

This companion summarizes valuation formulas already defined in `/app/docs/genealogy_policy.md`. When wording differs, `genealogy_policy.md` is authoritative.

Pattern genealogy reports combine weaver lineage, dye fidelity, and school continuity against each panel's pattern anchor from `/app/data/pattern_anchors/`.

Reports written to `/app/output/pattern_genealogy.json` must include:

- top-level `bundle_id` and `network_seal` (24 lowercase hex characters)
- `panels`: each row carries `panel_id`, `weaver_lineage` (6 dp), `dye_fidelity` (6 dp), `school_continuity` (4 dp), `heritage_score` (2 dp), and `influence_index` (2 dp)
- `summary`: `mean_influence` and `weakest_panel` (lowest `influence_index`)

`heritage_score = round(pattern_anchor * weaver_lineage * dye_fidelity * (letter_floor + letter_span * school_continuity / 100), 2)`

`influence_index = round((heritage_score / pattern_anchor) * 100, 2)`

Network-seal construction, dye-overlay merge into digests, `reset_drift` compounding, merchant `kind == "arms_length"` relay rules, and journal modes are defined in `/app/docs/genealogy_policy.md`, `/app/docs/dye_recipe_policy.md`, and `/app/docs/export_route_policy.md`.
