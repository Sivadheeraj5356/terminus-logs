# Inventory stage

Scientific computing inventory checkpoint for conserved vessel-mass projection estimators.
Path: `$CRYOREADY_STATE_DIR/inventory-stage.json` (default `/app/state/inventory-stage.json`).

Fields:

- `facility_id`, `assessment_epoch_unix`
- `facility_digest`, `catalog_digest`, `maintenance_digest` — SHA-256 hex of the raw input file bytes
- `vessels` — sorted by `vessel_id`, each row includes:
  - identity: `vessel_id`, `model_id`, `cryogen`, `cryogen_class`
  - `level_liters`, `fill_fraction`, `pressure_psig`, `pressure_psia`, `hold_hours`
  - `sensor_calibrated_until_unix`
  - `ready` (boolean) and `reasons` (string array)
- `inventory_digest` — SHA-256 hex of the canonical compact JSON of the stage fields excluding `inventory_digest` itself (object keys sorted recursively, then `dump()` with no extra whitespace)

## Per-vessel evaluation

`pressure_psia = pressure_psig + 14.6959`. Pressure is OK when `pressure_psia <= model.mawp_psia`.

Sensor calibration is OK when `sensor_calibrated_until_unix > assessment_epoch_unix` (exact equality is expired).

Hold time:

```
reserve = usable_capacity_l * hold_reserve_fraction
remaining = level_liters - reserve
hold_hours = 0 if remaining <= 0 else (remaining / boil_off_l_per_day) * 24
```

Rounding (required for digest agreement): after computing `fill_fraction`, `hold_hours`, and `pressure_psia` with the formulas above (and fill as in catalog-schema.md), round each value to **6 decimal places** via `round(value * 1e6) / 1e6` before writing the vessel row and before those fields participate in `inventory_digest`. Unrounded intermediate values must not appear in the stage JSON.

Reasons (any present ⇒ `ready=false`):

- `in_maintenance`
- `sensor_cal_expired`
- `fill_below_min` / `fill_above_max`
- `pressure_exceeds_mawp`
