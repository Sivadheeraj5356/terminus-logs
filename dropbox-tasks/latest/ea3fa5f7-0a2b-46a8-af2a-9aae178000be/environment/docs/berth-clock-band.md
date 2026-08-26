# berth clock band

Optional habitat policy input that constrains the tide contribution to the berth clock before any lane offset or wave padding is applied.

## habitat field

| Field | Type | Notes |
|-------|------|-------|
| berth_clock_band | object | Optional. Keys min and max (numbers). When absent, no clamp applies. |

Included in mission_hash like every other habitat field (see habitat-profile.md).

## rule

For each tide snapshot act, after berth_start is computed from dock_min and tide_ms (see tide-offset-windows.md) and rounded to six decimals:

1. When berth_clock_band is present: berth_start = min(max(berth_start, berth_clock_band.min), berth_clock_band.max), then round berth_start to six decimals.
2. Recompute berth_end = round(berth_start + transfer_min, 6).

When berth_clock_band is absent, leave berth_start and berth_end unchanged.

## ordering (precedence)

This is step 1 of the mandatory pipeline in tide-offset-windows.md. The clamp acts on the tide contribution only. Apply it BEFORE the lane-window-offset.md offset and BEFORE the wave-buffer.md padding.

A lane-window offset added afterward may move berth_start outside the band. That is expected and the value is not re-clamped. Applying the clamp after the lane-window offset is incorrect.

## tide_hash after clamp

Recompute tide_hash over the adjusted acts using the same digest rules as tide-snapshot.md.
