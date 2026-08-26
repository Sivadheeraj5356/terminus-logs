# wave buffer

Apply optional high-wave transfer padding as step 3 of the clock adjustment order in tide-offset-windows.md. Run this after berth-clock-band.md and lane-window-offset.md. Wave buffer changes transfer_min and berth_end only; it does not change berth_start.

## habitat fields

| Field | Type | Notes |
|-------|------|-------|
| wave_buffer_threshold | number | When absent, no buffer applies |
| wave_buffer_min | number | Minutes added to transfer_min when threshold is set |

## rule

For each act in the tide snapshot:

1. When wave_buffer_threshold is present and act wave_m is greater than or equal to wave_buffer_threshold:
   - transfer_min = round(transfer_min + wave_buffer_min, 6)
   - berth_end = round(berth_start + transfer_min, 6)
2. Otherwise leave transfer_min and berth_end unchanged.

Apply wave buffer after lane-window-offset.md and before writing /app/state/tide-snapshot.json. Do not apply wave buffer before the band clamp or lane offset.

## tide_hash after buffer

After this final adjustment step, recompute tide_hash over the adjusted acts using the same digest rules as tide-snapshot.md.
