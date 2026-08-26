# Equipment catalog

Scientific computing equipment-model inputs for cryogenic fill, hold, and MAWP gauges.

JSON object with `models` array. Each model:

- `model_id`
- `cryogen_class` (`LN2` or `LHe`)
- `gross_capacity_l`
- `usable_capacity_l`
- `mawp_psia` (maximum allowable working pressure, absolute)
- `setpoint_k`
- `boil_off_l_per_day`
- `min_fill_fraction` / `max_fill_fraction` (relative to usable capacity)
- `hold_reserve_fraction` (fraction of usable capacity reserved and unavailable for hold-time)

Fill fraction uses usable capacity only:

`fill_fraction = level_liters / usable_capacity_l`

After computing, round `fill_fraction` to 6 decimal places (`round(value * 1e6) / 1e6`) before range checks are recorded on the stage and before digest inclusion (see inventory-stage.md).

Fill is in range when `min_fill_fraction <= fill_fraction <= max_fill_fraction` using the rounded value.
