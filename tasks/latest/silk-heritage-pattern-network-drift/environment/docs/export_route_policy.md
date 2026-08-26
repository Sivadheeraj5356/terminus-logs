# Parish assignment attestation policy

School continuity is the percent of export-route timeline years that hold a valid loom letter. Count integer years from the first export-route `from_year` through the last `to_year` inclusive within the panel's clipped export-route span (after any incremental replay floor slice).

Mark a year covered when the owner during that year holds a letter whose `issued_year` through `expires_year` range includes the year.

When direct coverage fails on a transfer year, the prior owner may cover that year only if all of the following hold:

- the prior owner held a letter with `transfers_with_sale` true that was valid at the transfer year
- `/app/data/merchant_transfers/` contains a sale for that panel whose `year`, `seller`, and `buyer` match the transfer
- that sale's `kind` field equals the string `"arms_length"` (string equality; not a boolean flag)

Evaluate coverage per calendar year across the clipped, replay-sliced export-route span. Do not infer coverage from the final owner alone. Do not ignore the sales list or the relay predicate when computing continuity.

Publish `school_continuity` as a percentage on `[0, 100]` rounded to **four** decimal places.
