# crossdate-sizing data dictionary

These files describe forty tree-ring sites (`site_id` ts-01..ts-40) in one coring program and how
earlier cores at each have fared. A single increment core taken at a site either yields a ring
series that crossdates against the regional master or it does not, and that outcome falls at a
per-core rate `p` belonging to the site. Cores are independent, so taking `n` of them lands at
least one crossdate with probability `1 - (1 - p)^n`.

`sites.csv` gives one row per site. `sensitivity` is a reconnaissance reading of the site's
ring-to-ring signal from a preliminary look, and the per-core crossdate rate rises with it.
`field_cost` and `contract_cost` are that site's per-core prices on the two coring routes.

`core_log.csv` records the cores taken so far, one row per core. `crossdated` is 1 when that core
produced a series that dated against the master and 0 otherwise. Row counts differ widely from
site to site: a few carry long runs, many only one or two, and some were cored repeatedly with no
crossdate at all.

`chronology_policy.json` holds `reference_sensitivity` (a baseline sensitivity value),
`cross_rate_min` and `cross_rate_max` (the interval any inferred crossdate rate must lie in),
`anchor_floor` (the level every site must reach), `field_core_budget` (the shared field-core
ration), and `cost_ceiling` (the cap on committed cost).

The two routes differ only in price and supply. A field-crew core is billed at `field_cost` and
drawn from the shared `field_core_budget`, one ration serving all forty sites; a contract core is
billed at `contract_cost` with no limit on how many a site may take. Committed cost adds up
`field_cost` for each field core and `contract_cost` for each contract core over every site, and
a plan is valid only while that total stays at or below `cost_ceiling`.
