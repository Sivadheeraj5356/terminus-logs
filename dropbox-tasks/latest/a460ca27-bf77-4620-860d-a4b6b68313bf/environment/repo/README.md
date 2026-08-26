# haul-permit-report

A small offline data-processing tool that turns haul-permit telemetry
into a billing-style ledger report. It ingests a timestamped stream of
data-traffic and credit events together with per-truck and per-quarry
throttle/cap allowances (with surge timers and a bounded shared family reserve
pool) and emits a deterministic ledger of traffic verdicts, surge-state
transitions, and reserve-pool activity.

```
python3 report.py <quarry-config> <traffic-stream>
```

The required output covers the truck-and-quarry conjunction, the throttle/cap
limits, the surge-window lifecycle, the inclusive surge boundary, the shared
quarry reserve pool with borrow/repay debt, and the canonical ledger ordering. It is
described in [docs/spec.md](docs/spec.md). The report builder lives in
[report.py](report.py): the argument handling, file reading, parsing, and
printing are fixed, and only the `build_ledger` transformation needs to be
completed.
