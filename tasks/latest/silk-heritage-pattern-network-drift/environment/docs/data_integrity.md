# Data integrity

Runtime registries under `/app/data/` are pinned for valuation compiles. Do not modify pinned registry files during dye-recipe work. Companion integrity digests may be recorded as `data_integrity.json` beside verifier helpers.

When `TRACE_DATA_ROOT` points at an alternate registry tree, loads and seal digests must follow that tree. Leave the pinned `/app/data/` tree unchanged. Registry directories such as `/app/data/export_routes` participate in attestation.

Restoration amendment overlays under `/app/data/dye_reformulations/overrides/` (or the matching path under `TRACE_DATA_ROOT`) are merged into the base dye-recipe registry when the registry cache loads dye-recipe events.
