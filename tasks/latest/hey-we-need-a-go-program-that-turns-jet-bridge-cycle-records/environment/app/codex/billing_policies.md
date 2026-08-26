billing policy notes

base fee comes from airframe_rates with the entry whose effective_from is at or before the timestamp under consideration. when more than one entry matches the latest is used. the base fee equals base_cents plus per_minute_cents multiplied by dwell_minutes.

off hours uplift is the per zone offhours_pct_bps from gate_zones.json applied as basis points of the base fee. the uplift is computed as base_fee_cents times bps divided by ten thousand using integer arithmetic that drops the remainder. the net billable on an off hours cycle is base plus uplift.

holdover doubles the base fee for the resolved tier and does not take any off hours uplift even if the inblock falls inside the off hours window. holdover billing still counts toward the monthly cap for purposes of breach detection on subsequent cycles.

the monthly cap is per carrier_iata and gate_zone and is keyed by the year and month parsed from actual_inblock_ts. crossing the cap on a cycle causes that cycle to bill normally, but every subsequent cycle for the same carrier and gate zone in the same month is recorded with verdict capped overage and a zero net. holdover overrides cap behaviour and bills at twice the base.

stale tier is decided strictly on the effective_from string of the active row at the two timestamps. equality of the effective_from strings is the only success criterion.

verdict precedence governs which of these rules wins when several could fire on the same cycle id. see cycle_codex for the ordered list. tests assert each precedence transition independently.
