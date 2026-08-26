You administer the site's software license-seat station, which provisions entitlement seats to onboarding accounts from the pool of covered seats. Its overnight allocation stage is unfinished: finish `/app/license/` so the night's request feed turns into the JSON allocation file the morning operators work from:

node /app/bin/seat-allocate /app/data/onboarding_requests.ndjson /app/out/allocation.json

The first argument is the feed of seat requests, suspensions, restores, and cancels. The second argument is the file to write; create the directory if it is missing. Always load the seat inventory, entitlement rules, and station config from `/app/data`, even when the feed path is different.

The contract in /app/docs/seat-allocate.md is the source of truth. Keep the command arguments, the output shape, and the documented exports from `/app/license/` stable.

Headline behaviors, all pinned in the contract: the whole feed settles before any seat moves, and cancels resolve to a fixpoint where a cancel of a cancel puts the request back; suspensions lift per restore, one suspension at a time; entitlement comes from the rules file, and exact-edition tiers tighten it; a seat whose coverage ends on the allocation date itself is out, and a request's `activeUntil` horizon tightens which seats it can take; fills are whole-demand or nothing; and the worked reservation case shows a batch where handing the earliest-covering seat to the first request would leave a later request with nothing it can accept, and what the batch allocates instead. The output top level is exactly `events`, `allocations`, `unusedSeats`, and `summary`.
