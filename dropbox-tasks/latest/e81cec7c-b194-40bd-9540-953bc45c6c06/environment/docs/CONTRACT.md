# Scientific computing cryogenic bay weight-conservation contract (`/app`)

This document states **scientific computing** conservation laws for conserved-mass
projection estimators under inventory-checkpoint resume. Properties below are
scientifically required invariants for Monte Carlo-style cryogenic bay conservation
experiments, projection-estimator bias checks, and checkpoint-resume measurement
validity — when they fail, readiness summaries are scientifically invalid.

Detailed gauge formulas and schemas live in the peer docs linked below. This
contract is the authoritative conservation summary.

## Conserved vessel-mass gauges (inventory checkpoint)

After a successful `cryoready inventory` trial:

- Fill projection uses **usable** capacity only:
  `fill_fraction = level_liters / usable_capacity_l`, never `gross_capacity_l`.
- Hold projection subtracts reserve before boil-off:
  `remaining = level_liters - usable_capacity_l * hold_reserve_fraction`;
  `hold_hours = 0` if `remaining <= 0`, else `(remaining / boil_off_l_per_day) * 24`.
- Pressure projection converts gauge to absolute before MAWP:
  `pressure_psia = pressure_psig + 14.6959`; pressure is OK when
  `pressure_psia <= model.mawp_psia`.
- Computed `fill_fraction`, `hold_hours`, and `pressure_psia` are rounded to
  **six decimal places** via `round(value * 1e6) / 1e6` before stage JSON and
  before `inventory_digest` inclusion.
- Maintenance windows are half-open `[start, end)`; the end instant is not blocked.
- Sensor calibration is valid only when `calibrated_until > assessment_epoch_unix`
  (equality is expired).
- The inventory checkpoint at `$CRYOREADY_STATE_DIR/inventory-stage.json` binds
  `facility_digest`, `catalog_digest`, and `maintenance_digest` to raw input bytes
  and includes an `inventory_digest` over the canonical stage body.

See `/app/docs/inventory-stage.md`, `/app/docs/catalog-schema.md`,
`/app/docs/maintenance-schema.md`, `/app/docs/facility-schema.md`.

## Placement projection and certificate gauges (assess resume)

After a successful `cryoready assess` trial that resumes from a fresh inventory
checkpoint:

- A vessel meets a request only when it is `ready`, cryogen-class compatible
  (exact LN2/LHe match), and `hold_hours >= min_hold_hours`.
- Preferred vessels may be assigned only when they meet those eligibility gauges;
  otherwise assignment falls back to lexicographically eligible vessels.
- `certificate_ok` is true only when every placement request is satisfied.
- Assess refuses missing or stale inventory checkpoints with exit status 2 and
  stderr mentioning inventory.

See `/app/docs/readiness-report.md`, `/app/docs/certificate-contract.md`,
`/app/docs/cli-surface.md`.

## Durable measurement ledger

Ledger path defaults to `/app/var/cryoready-ledger.json` (overridable).

- Assess/inventory counters key on the composite digest
  `facility_digest|catalog_digest|maintenance_digest`.
- `assess_runs` increments on every successful assess save for that key, even when
  the report digest repeats.
- `write_seq` advances on every successful save.
- Truncated or corrupt ledger files recover the longest salvageable JSON prefix
  that yields an object with `entries`; otherwise start empty.

See `/app/docs/ledger-contract.md`.
