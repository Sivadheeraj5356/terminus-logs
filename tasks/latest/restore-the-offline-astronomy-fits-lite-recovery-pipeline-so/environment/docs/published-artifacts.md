# Published artifacts

`tile-order.manifest` is a newline-separated list of committed tile ids in
authority order. `mosaic-contours.svg` is generated from the final
`PRIMARY_IMAGE` using `/app/data/contour-thresholds.tsv`; cells are emitted in
row-major order for each threshold.

`reconciliation-report.json` records `calibration_profile`,
`calibration_epoch`, `weighted_flux_total`, `contours_regenerated`, and one
sample object for every row in `/app/data/world-samples.tsv`.
`contours_regenerated` is true when the SVG was generated from the final
mosaic during the publish. Sample coordinates use the final mosaic's global WCS
and report zero image and coverage outside the grid.

`recovery-status.json` records completion state, expected tile order, committed
tiles, resumed tiles, rolled-back record tile ids, and published artifact names.
