# Conventions

These rules keep the calculator deterministic and its output stable.

- Every monetary amount is an integer number of micro-units of a major currency
  (1000000 micro-units per major unit); every rate is an integer number of basis
  points, where 10000 basis points is a full 100 percent. No floating point is
  used anywhere.
- The database at `/app/data/crosspay.db` is the single source of truth for
  employees and logged hours. `init` is idempotent.
- A statutory schedule is a progressive set of tiers ordered by ascending bound.
  Each tier charges its marginal rate on the slice of gross that falls inside it;
  the highest tier is open-ended.
- The reported amount for a country run is expressed in that currency's own
  minor unit. Different currencies carry different minor units, so the same gross
  can round differently depending on the country.
- The `country-info`, `country-pay`, `social` and `report` commands read the
  bundled dataset; every command is offline. Their inputs are pinned ISO country
  codes (see `docs/spec.md`).
- The employer social contribution charges a region rate on a contributory base,
  which is the gross raised to at least the country floor and then lowered to at
  most the region cap (the cap wins when a floor exceeds it). The region rules
  and country floors are constants in `contrib.go`.
- Amounts reach the reporting base currency only through the pivot currency, one
  rounded leg to the pivot and one rounded leg to the base; a direct source to
  base conversion is not used. The cross-rate table is in `fx.go`.
- The report ranks countries by base cost descending, then employee count
  descending, then country code ascending.
- All machine-readable tokens, including error statuses, are written to stdout.
  Stderr carries only the usage banner. Failures exit non-zero.
