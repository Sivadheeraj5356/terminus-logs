# tide offset windows

Berth clock start combines dock_min with signed tide_ms from each cargo row.

Formula:

```
berth_start = dock_min + tide_ms / 60000
```

tide_ms is in milliseconds. Negative values shift berth_start earlier than dock_min. Positive values shift later.

Round berth_start to six decimal places.

Initial transfer_min comes from wave-scaling.md (`base_min * wave_m`, round 6). berth_end equals berth_start plus transfer_min, also rounded to six decimal places, and is recomputed after every later adjustment that changes berth_start or transfer_min.

The tide_ms field in tide snapshot acts must preserve the original signed integer from cargo.jsonl.

## clock adjustment order (mandatory pipeline)

After the base berth_start and transfer_min formulas above, apply optional habitat policies in this exact order. Do not reorder, skip, or merge steps. Do not re-apply an earlier step after a later one.

1. berth_clock_band clamp on berth_start (see berth-clock-band.md). Recompute berth_end from the clamped berth_start and the current transfer_min.
2. lane_window_min offset on berth_start (see lane-window-offset.md). Recompute berth_end. Do not re-clamp into the band after this offset.
3. wave_buffer padding on transfer_min when the wave threshold is met (see wave-buffer.md). Recompute berth_end from the (possibly offset) berth_start and the padded transfer_min.

Recompute tide_hash only after all three steps finish (see tide-snapshot.md). ROV scheduling and berth assignment must read the final adjusted acts.

Wrong order examples that break digests: applying lane_window before berth_clock_band; clamping again after lane_window; applying wave_buffer before lane_window; hashing tide acts before wave_buffer.

Always recompute berth_end from the current berth_start and transfer_min after any step that changes either value.