# Mosaic reduction model

`/app/data/run-config.tsv` defines the global grid, global WCS, active
calibration profile, and active calibration epoch. Calibration rows are selected
by tile id, profile, and epoch. Directory order is not an authority.

For each tile pixel at local coordinates `(i,j)`, compute world coordinates from
the tile's WCS. `WCS_MODE=ALT` uses `ALT_CRVAL*` and `ALT_CDELT*`; other modes
use primary `CRVAL*` and `CDELT*`. Grid coordinates round
`(world - global_crval) / global_cdelt`. In-bounds pixels add `pixel * weight`
to the flux accumulator, add `weight` to the weight accumulator, increment
coverage, increment that tile's contributed cell count, and add to
`weighted_flux_total`. `PRIMARY_IMAGE` is accumulated flux divided by
accumulated weight, or zero for empty cells.
