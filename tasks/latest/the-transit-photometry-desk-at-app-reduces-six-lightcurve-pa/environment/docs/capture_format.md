# Capture format

Bundle lines:

- `cursor` — cadence index at capture
- `saved_stride` — archival workspace pitch
- `phase` — running mixer state
- `bins` — phase-bin count
- `width_b` — aperture apron width
- `cells` — densified phase-bin values

Restores must reconstitute the active stride before advancing past the
snapshot. Repeated restores of one bundle must reconstruct the same live
workspace.
