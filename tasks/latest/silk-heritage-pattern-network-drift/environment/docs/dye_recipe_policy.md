# Dye recipe policy

Dye fidelity factor starts at `1.0`, or at a sequential drift seed when the bundle declares `panel_coupling` (see `/app/docs/genealogy_policy.md`). For every eligible dye reformulation on the panel ordered by `year`, multiply the running factor by `(1 - dye_penalty_rate * severity)` using the penalty rate from `/app/config/weights.toml`. When a reformulation row sets `reset_drift` to true, set the running factor to exactly `1.0` at that year before processing later rows (ignore `severity` on reset rows). Each event compounds multiplicatively; do not sum penalties and subtract once from `1.0`.

A dye reformulation enters the compounding sequence only when all of the following hold:

- its `year` falls inside an export_routes epoch with `export_eligible` true (when the field is absent, treat the epoch as eligible)
- `/app/data/school_recitals/` contains at least one recital record for the canonical panel whose `year` is less than or equal to the reformulation `year`

Determine export-route and school-recital eligibility before compounding begins. Reformulations outside eligible windows must be excluded first. Publish `dye_fidelity` rounded to six decimal places and keep the factor inside `[0, 1]`.

## Registry field semantics

- `canonical_id`: resolved catalog key after following `alias_of` links in `/app/data/panels/`.
- `weaver_id`: master weaver id on the canonical panel row used for lineage walks.
- `completion_year`: panel year used when filtering succession hops.
- `base_appraisal`: pattern-anchor appraisal scalar from `/app/data/pattern_anchors/` for the canonical panel.
- `owner_id` / `holder`: export-route epoch owner and loom-letter holder strings used in coverage.
- `mentor_of`: weaver genealogy map in `/app/data/master_weavers/` traversed by lineage compile.
- `severity`: dye reformulation severity multiplier applied by the fidelity compounding step.
- `reset_drift`: when true, zeroes the running dye factor to `1.0` at that year.
- `kind`: merchant-transfer string; relay sales must equal `"arms_length"`.
- `rotation_id`: integer tag on rotation fixture segments used when classifying incremental replay windows.
- Blend coefficients `letter_floor`, `letter_span`, and `dye_penalty_rate` are read from `/app/config/weights.toml` per policy family.

## Dye amendment overlays

Late curator amendments under `/app/data/dye_reformulations/overrides/` extend the base dye reformulation registry. Merge amendment rows into the canonical reformulation slice for each panel before timeline clipping, dye gating, compounding, and network-seal digest materialization. Digests that omit overlay rows are invalid.
