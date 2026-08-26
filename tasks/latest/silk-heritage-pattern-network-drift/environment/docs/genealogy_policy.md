# Pattern genealogy policy

Pattern genealogy reports combine weaver lineage, dye fidelity, and loom-letter school continuity against each silk panel's base pattern anchor from `/app/data/pattern_anchors/`. For each panel row, `heritage_score` is derived from the pattern anchor multiplied by `weaver_lineage`, `dye_fidelity`, and the letter blend term `letter_floor + letter_span * (school_continuity / 100)`, rounded to two decimals, and therefore always lies between the floor-only and full-span products of those terms. `influence_index` is `heritage_score / pattern_anchor * 100`, also rounded to two decimals.

## Published field precision

Round published panel fields as follows before writing `/app/output/pattern_genealogy.json`:

- `weaver_lineage`: six decimal places
- `dye_fidelity`: six decimal places
- `school_continuity`: **four** decimal places (percentage on `[0, 100]`; do not round to two decimals)
- `heritage_score` and `influence_index`: two decimal places

Reports written to `/app/output/pattern_genealogy.json` must include:

- top-level `bundle_id` and `network_seal` (24 lowercase hex characters)
- `panels`: each row carries `panel_id`, `weaver_lineage`, `dye_fidelity`, `school_continuity` (0–100, four decimal places), `heritage_score`, and `influence_index`
- `summary`: `mean_influence` and `weakest_panel` (lowest `influence_index`)

Summary `mean_influence` is the arithmetic mean of panel influence indices rounded to two decimals. Summary `weakest_panel` names the panel with the lowest `influence_index`. When several panels share that minimum, choose the first row in bundle panel declaration order.

Published reports echo the bundle's `bundle_id` and list `panels` in the same order as the bundle declaration.

## Policy families

Bundles may declare `policy_family`. When absent, use the default `[genealogy_blend]` section of `/app/config/weights.toml`. When present, read blend coefficients from `[genealogy_blend.<policy_family>]` for that compile. Consecutive traces in one interpreter must load the correct section for each bundle; do not reuse a prior family blend table.

## Network seal

Every report carries a `network_seal` so halted runs can replay without drift.

**Policy family label.** If the bundle JSON omits `policy_family`, use the literal string `standard` in seal input and load `[genealogy_blend]`. Otherwise use the declared family name and load `[genealogy_blend.<policy_family>]`.

**Registry digest.** At compile time assemble one `catalogs` object with these eight keys: `master_weavers`, `dye_reformulations`, `export_routes`, `loom_letters`, `pattern_anchors`, `panels`, `merchant_transfers`, and `school_recitals`. Load each registry directory by merging its `*.json` files in sorted filename order. For `dye_reformulations`, also append every row from `/app/data/dye_reformulations/overrides/*.json` onto the matching panel id so overlays participate in both dye gating and the seal digest. Serialize with `json.dumps(catalogs, sort_keys=True, default=str)` and **do not** pass compact `separators=(",", ":")`; keep JSON default spacing after `:` and `,`. Take the first 16 hexadecimal characters of SHA-256 over that UTF-8 string.

**Panel manifest digest.** Hash the comma-joined `panel_id` values from the bundle declaration in list order (no spaces). Take the first 8 lowercase hexadecimal characters of SHA-256 over that UTF-8 string.

**Final seal.** Join five pipe-separated fields: bundle `bundle_id`, the policy family label from above, the snapshot cutoff year as a decimal string or the literal `None` when `genealogy_snapshot.as_of_year` is absent, the registry digest, and the panel manifest digest. Take the first 24 lowercase hexadecimal characters of SHA-256 over that joined string. The published `network_seal` uses only lowercase characters from `0123456789abcdef`.

## Weaver lineage walks

Lineage weight starts at `1.0`. Walk `mentor_of` links from the panel weaver toward the root, multiplying each hop's `thread_trust`. Only take a hop when the panel `completion_year` is greater than or equal to that hop's `active_from_year` in `master_weavers/succession_epochs`. Compile the active successor map from the panel `completion_year` at walk time using the raw `mentor_of` map together with the full master-weavers registry; do not precompile a successor map that ignores `completion_year`.

## School continuity and merchant relay

School continuity is the percent of clipped export-route years covered by a valid loom letter. When direct coverage fails on a transfer year, the prior owner may cover that year only when that owner held a letter with `transfers_with_sale` true at the transfer year **and** `/app/data/merchant_transfers/` contains a sale whose `year`, `seller`, and `buyer` match the transfer and whose `kind` field is the string `"arms_length"` (not a boolean). Publish `school_continuity` rounded to four decimal places.

## Sequential panel drift coupling

Bundles may declare `"panel_coupling": "sequential_drift"`. Compile panels in bundle declaration order. The first panel compounds dye fidelity from `1.0`. Each later panel seeds its gated reformulation compounding from the prior panel's rounded `dye_fidelity` (six decimal places), not from `1.0`. Bundles without this field treat every panel independently.

When a reformulation row sets `reset_drift` to true, reset the running dye factor to `1.0` at that year before later rows (see `/app/docs/dye_recipe_policy.md`).

Panel catalog rows may declare `alias_of`; resolve to the canonical panel record before loading registry slices. Report rows use the bundle panel id even when an alias was resolved internally. Dye gating, export-route epochs, school recitals, and pattern anchors must use the canonical id after alias resolution.

Dye fidelity factors are multiplicative products and stay within `[0, 1]`. School continuity stays on the `[0, 100]` percentage scale.

When the environment variable `TRACE_DATA_ROOT` is set, registry loads (including seal digests and dye overlays) resolve relative to that directory instead of `/app/data`. Pinned runtime catalogs under `/app/data/` must not be mutated.

## Tracing journal modes

- `TRACE_INCREMENTAL=1` — incremental rotation-segment replay; school continuity must honor the derived replay floor.
- `TRACE_HALT=1` writes a full computed report to `/app/output/.genealogy_journal.json` and must not write the `--out` path; after a halt run the `--out` file must be absent (`exists()` is false).
- `TRACE_RESUME=1` publishes the committed journal body when its `network_seal` still matches a fresh compile; otherwise performs a full cold compile before writing `--out`.
- With no journal on disk, resume matches a plain trace.
- A cold compile followed by `TRACE_RESUME=1` must agree with a single cold compile for the same bundle and registries when the journal is absent or its seal is stale.

Detailed phase ordering, snapshot clipping, dye-recipe gating, and export-route attestation rules live in the companion docs under `/app/docs/`.
