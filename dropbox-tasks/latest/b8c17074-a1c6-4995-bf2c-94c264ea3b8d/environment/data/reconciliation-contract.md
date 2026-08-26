# FITS-LITE recovery contract

The files under `/app/data` are immutable authorities. `run-config.tsv` is a
`key`/`value` table with `profile`, `epoch`, `width`, `height`, `crval1`,
`crval2`, `cdelt1`, and `cdelt2`. `tile-order-authority.tsv` has
`order_index`, `tile_id`, and `phase` columns. `world-samples.tsv` has
`sample_id`, `world_x`, and `world_y`. Tile files use key/value headers with
`TILE_ID`, `WCS_MODE`, `WIDTH`, `HEIGHT`, `CRVAL1`, `CRVAL2`, `CDELT1`,
`CDELT2`, optional legacy primary keys, `ALT_CRVAL1`, `ALT_CRVAL2`,
`ALT_CDELT1`, and `ALT_CDELT2`, plus a `PIXELS` block. `WCS_MODE=ALT` makes the
ALT keys authoritative for placement; other modes use primary WCS keys.

`calibration.tsv` may contain several rows for the same tile. The row selected
for reduction is the one matching tile id, active profile, and active epoch.
`journal/resume.tsv` records prepared, committed, and interrupted work. A
commit is a reusable prefix record only when it matches the next tile in
authority order; later prepared, crashed, or out-of-prefix records are discarded
and reported by the recovery status.

Published artifacts in `/app/work` are generated from the recovered mosaic.
`mosaic.fits` uses FITS-LITE 2 HDUs. `PRIMARY_IMAGE` is a weighted average
derived from active calibration and tile WCS, `COVERAGE` counts in-bounds
contributing pixels, `CHECKPOINT` includes `RUN_PROFILE`, `CALIBRATION_EPOCH`,
`EXPECTED_TILE_ORDER`, `COMMITTED`, and `RECOVERY_SOURCE`, `PROVENANCE` has one
`TILE` row per committed tile with `order_index`, `phase`, selected weight, WCS
mode, and contributed cells, and `CHECKSUMS` are FNV64 values over final HDU
text. `tile-order.manifest` lists committed tile ids one per line,
`mosaic-contours.svg` uses the thresholds in `contour-thresholds.tsv`, and
`reconciliation-report.json` includes `calibration_profile`,
`calibration_epoch`, `weighted_flux_total`, `contours_regenerated`, and samples
the final mosaic at every coordinate in `world-samples.tsv`.
`recovery-status.json` uses `status="complete"` with `expected_tile_order`,
`committed_tiles`, `resumed_tiles`, `rolled_back_records`, and
`published_artifacts`.

Numeric comparisons use a `1e-6` tolerance. A uniform scaling of every active
calibration weight preserves the weighted-average image and coverage while
scaling `weighted_flux_total` and provenance weights by the same factor. The
`sample` command reports the final mosaic image value at an in-bounds world
coordinate and rejects coordinates outside the grid.
