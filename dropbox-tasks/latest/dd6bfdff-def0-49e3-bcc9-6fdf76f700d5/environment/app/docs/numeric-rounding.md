# Numeric rounding (r3)

Computed tonne totals, rates, and imbalance percentages in staged and reported outputs use the rounding helper r3. Integer counters such as total_tanks are not rounded with r3.

## Raw gauged snapshot fields (no r3)

opening_mass_tonnes and closing_gauged_tonnes are copied verbatim from inventory_snapshots.csv gauged_mass_tonnes for the earliest and latest snapshot of each tank. Do not apply r3 to those two fields; leave the snapshot values as parsed from input.

## Definition

r3(value) means round(value + 1e-9, 3) — three decimal places after the decimal point, with a positive 1e-9 epsilon bias before rounding. That bias is part of the product contract so half-up ties at the third decimal are stable (plain rounding without the bias can be off by 0.001 in edge cases).

In Go this is equivalent to math.Round((value + 1e-9) * 1000) / 1000.

## Where r3 applies

Apply r3 to:

- instantaneous bog_rate_tonnes_per_hour for each eligible reading before that rate is used in time integration
- total heat_leak_bog_tonnes per tank after trapezoidal integration (or the single-reading rule below)
- relief_bog_tonnes after summing relief transfer masses
- transaction_delta_tonnes after summing delivery, withdrawal, and regas contributions
- expected_closing_tonnes after opening mass plus transaction delta minus total calculated boil-off
- imbalance_pct after the percent formula when closing gauged mass is non-zero
- corrective action value strings formatted with three decimals after r3 on the underlying field

Do not apply r3 only to the final heat-leak total while leaving per-reading bog rates unrounded. Trapezoidal segments must use already-rounded endpoint rates.

## Interaction with heat-leak integration

See /app/docs/heat-leak-bog.md for wetted area, kelvin delta, and trapezoidal weighting. The per-reading rate returned from the bog rate formula must be r3-rounded before it participates in any segment average or single-reading shortcut.
