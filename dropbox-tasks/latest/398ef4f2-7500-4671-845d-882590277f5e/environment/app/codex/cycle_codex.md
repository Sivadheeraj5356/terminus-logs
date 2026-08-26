cycle lifecycle and verdict catalogue

every processed row carries exactly one verdict drawn from this catalogue.

CLEARED means the cycle priced and billed inside its monthly cap with no special handling.

OFFHOURS_PREMIUM means the actual inblock time fell inside the off hours window declared in feebook/offhours_window.toml. the start of the window is exclusive at second precision and the end is inclusive. the uplift is applied to the base fee and the result is the net billable.

HOLDOVER_REBILL means status holdover is the latest status posted for a cycle id. the bridge cycle was held over from a prior assignment and the net fee is exactly twice the base fee for the resolved tier. holdover overrides any monthly cap behaviour for that cycle.

STALE_TIER means the airframe rate row active at gate_assigned_ts is not the same row active at actual_inblock_ts. the cycle cannot be priced because the contract is silent on which side wins. the tier_version column on a STALE_TIER row still carries the effective_from string of the row active at gate_assigned_ts, so downstream reviewers can see which tier was attempted.

CAPPED_OVERAGE means the cumulative billed cents for the carrier and gate zone within the same calendar month has already crossed the monthly cap from gate_zones.json before this cycle. the cycle still appears on the billing line with a zero net but does not add to the cumulative total. the cycle that first crosses the cap is not itself CAPPED_OVERAGE; it bills at its full net and its net still feeds the cumulative total. every subsequent cycle for the same carrier and gate zone within the same calendar month is then recorded as CAPPED_OVERAGE.

REJECTED_NUMERIC means mtow_tons arrived as a non integer numeric value. the schema requires whole tons.

REJECTED_TIER means body_code is not one of NB, WB, or RJ.

VOID_DUPLICATE means two or more rows share a cycle id but disagree on mtow_tons. the cycle cannot be billed because the airframe weight cannot be reconciled. when duplicates agree on mtow_tons, the latest row by actual inblock time wins the status and the dwell, and the mtow comes from the earliest row by the same key.

verdict precedence when more than one rule could fire on the same cycle id reads as numeric anomaly first, then tier anomaly, then duplicate void, then holdover, then stale tier, then capped overage, then off hours, then cleared.
