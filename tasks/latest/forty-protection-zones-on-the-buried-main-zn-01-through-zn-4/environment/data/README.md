# anode-stringing input files

Three files describe forty cathodic-protection zones (`zn-01` through `zn-40`) on one buried main. A
zone holds while any one anode strung on it is still passing current at design-life end, and the
anodes wear through independently, so `n` anodes on a zone hold it with chance `1 - (1 - p)^n` for
that zone's per-anode survival probability `p`.

zones.csv, one row per zone:
  zone_id       the zone label, zn-01 through zn-40
  resistivity   the soil-resistivity reading taken on that zone's ground
  stock_cost    the per-anode price on the stock route
  extra_cost    the per-anode price on the expediter route

survival_log.csv, one row per anode already pulled from service (row order not meaningful):
  zone_id       the zone the anode came off
  lasted        1 if the anode was still passing current when pulled, 0 if it had worn through
  The rows are not shared out evenly. A zone might sit behind a long history of pulls or behind just
  two or three, and on some every anode pulled so far had already failed.

cp_policy.json, a flat object:
  reference_resistivity   a central resistivity level the per-zone readings are measured from
  survival_min            lower end of the band a per-anode survival chance must sit in
  survival_max            upper end of that band
  protection_floor        the design-life protection chance every zone must reach
  anode_stock_budget      count of stock-route anodes on hand for all forty zones together
  cost_ceiling            the cap on total committed cost
