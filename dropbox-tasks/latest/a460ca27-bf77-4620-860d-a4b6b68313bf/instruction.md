The directory /app holds a small offline data-processing tool that turns haul-permit telemetry into a billing-style ledger report. It ingests two structured text files (a quarry-config and a traffic-event stream) and replays the stream against the configured allowances to produce a deterministic ledger, one record per line on standard output.

Run it as:

    python3 /app/report.py <quarry-config> <traffic-stream>

Both arguments are paths to text files. The quarry-config declares truck and quarry allowances (each with a throttle threshold, an absolute cap, and a surge window in ticks, plus an optional quarry reserve-pool capacity) and maps each truck to one quarry. The traffic stream carries timestamped HAUL and RETURN events. Every traffic event must satisfy both the truck allowance and its quarry allowance; the most restrictive of the two decides, and each event is all-or-nothing. Caps are absolute; crossing the throttle threshold opens a per-allowance surge window; a shortfall may be borrowed from the quarry's shared reserve pool and later repaid by credits.

The provided `report.py` already parses and validates both input files, but its `build_ledger` step is only a placeholder: it echoes every HAUL as `PERMITTED` and applies none of the allowance model. Your job is to complete `build_ledger` so the report matches the contract exactly.

The complete output contract is specified in /app/docs/spec.md: the allowance model, the surge-window lifecycle (inclusive expiry, cancel and restart), the reserve-pool borrow and repay ordering, the exact output records and their canonical ordering (PERMITTED, DENY, SURGE_START, DRAW, REPAY), and error handling. Implement the transformation to match that contract exactly. Malformed input, an unknown truck, or any structural violation must write a diagnostic to standard error and exit with a nonzero status without printing a ledger.
