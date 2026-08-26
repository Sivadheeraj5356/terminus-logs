# Rate and recoupment

## Medium base rates

Path: `/app/config/rate_tiers.toml`

Section `[medium.<NAME>]` provides `baseRateMicroCents` for each allowed medium.

## Territory multiplier

Path: `/app/config/territory_calendar.json`

Each territory entry provides `multiplier` (integer, 10000 = 1.0000×).

## Rerun brackets

Section `[rerun]` in `rate_tiers.toml` contains `[[rerun.brackets]]` rows with:

- `maxRerunIndex` — inclusive upper bound
- `multiplier` — integer scale (10000 = 1.0000×)

Select the bracket with the smallest `maxRerunIndex` where `rerunIndex <= maxRerunIndex`. Brackets are listed in ascending `maxRerunIndex` order in the file.

## Recoupment caps

Path: `/app/config/recoupment_caps.json`

Nested map: `workId -> territory -> tier -> capMicroCents`

Tiers in waterfall order (first depleted first):

1. `distributor`
2. `producer`
3. `participant`

## Monthly recoupment

Reporting month `periodMonth` is `YYYY-MM` derived from `dayLocal`.

For each `(workId, territory, periodMonth)` group:

1. Sum `grossMicroCents` from all daily rows in that month (across mediums).
2. Apply the waterfall against outstanding caps (each tier absorbs up to its remaining cap).
3. `netPoolMicroCents = grossMonth - totalRecouped` (never negative total recouped; cap at gross).

Only `netPoolMicroCents` enters participant split. Daily and weekly artifacts report `recoupedMicroCents = 0`; recoupment appears only in escrow body lines via reduced participant totals (computed from net pool).

## Escrow period

The bundled pipeline uses a single escrow period: the latest `periodMonth` present in daily rows. Emit one footer for that period.
