# lane window offset

Apply optional per-lane berth clock offsets as step 2 of the clock adjustment order in tide-offset-windows.md. Run this after berth-clock-band.md and before wave-buffer.md. Do not apply lane offsets before the band clamp.

## lane_window_min

Optional object on habitat.json mapping lane label strings to minutes added to berth_start for cargo on that lane. When absent or empty, no offsets apply.

For each act in the tide snapshot:

1. Read offset = lane_window_min.get(act lane, 0)
2. When offset is non-zero: berth_start = round(berth_start + offset, 6)
3. Recompute berth_end = round(berth_start + transfer_min, 6)

Do not re-apply berth_clock_band after this offset. A lane offset may move berth_start outside the band; leave that value as-is.

Apply offsets before writing /app/state/tide-snapshot.json and before rov-index or berth-staging ingest stages run. Final tide_hash is computed only after wave-buffer.md as well (see tide-offset-windows.md).

## tide_hash after offsets

After the full adjustment pipeline finishes, recompute tide_hash over the adjusted acts using the same digest rules as tide-snapshot.md.
