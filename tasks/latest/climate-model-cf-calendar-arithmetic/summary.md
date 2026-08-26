# # Climate model CF calendar arithmetic

- **UUID:** `dcbfce51-fa5b-4d62-853f-ef64646cdd8f`
- **Slug:** `climate-model-cf-calendar-arithmetic`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Numerical time axes in climate and earth-system models follow CF conventions. An encoded day count must decode to the same calendar-qualified year-month-day under its declared calendar and units origin: 360_day years use twelve 30-day months; noleap years keep February at 28 days; Gregorian leap-year rules apply only when that calendar is declared.

Interval bounds and monthly climatological bins must use that same calendar arithmetic, not fixed Unix-day widths. The toolkit under `/app` must preserve those numerical instants when climate simulation members with different units origins are placed on one axis, including when an earlier committed prefix under `/data/segments/` has already been retired.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
