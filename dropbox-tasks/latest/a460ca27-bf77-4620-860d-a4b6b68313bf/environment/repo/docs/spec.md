# Haul-permit throttle report: contract

`report.py` replays a timestamped stream of data-traffic and credit events
against per-truck and per-quarry data allowances and prints a deterministic
ledger of traffic verdicts, surge-state transitions, and reserve-pool activity.

```
python3 report.py <quarry-config> <traffic-stream>
```

The two positional arguments are paths to text files. The ledger is written to
standard output, one record per line, terminated by a newline.

## Allowance model

Every allowance (whether it belongs to a truck or to a quarry) has three
integer parameters: a **throttle threshold** (`soft`), a **cap** (`hard`,
`hard >= soft >= 0`), and a **surge** window measured in ticks (`grace >= 0`).
Usage is a count of hauls, a non-negative integer that starts at `0`. A quarry line
may carry one extra integer parameter beyond these three, its **reserve pool**
capacity (`pool >= 0`, defaulting to `0` when the field is omitted); see the
reserve-pool section below.

Each truck belongs to exactly one quarry. Both the truck's own allowance
and its quarry's allowance are evaluated for every traffic event; a traffic event is
permitted only when **both** allowances permit it (most-restrictive wins).

An allowance is in one of three traffic regimes at any tick:

- **under throttle**: current traffic `<= soft`.
- **over throttle, within surge**: traffic `> soft` and the surge window has not
  yet expired. Usage events are still permitted (subject to the cap).
- **over throttle, surge expired**: traffic `> soft` and the surge window has
  expired. The throttle threshold now behaves like a cap.

The **cap is absolute**: a traffic event that would drive traffic strictly above
`hard` is rejected immediately, regardless of surge state.

## Surge-timer lifecycle

Each allowance carries an independent surge timer. The truck timer and the
quarry timer never share state.

- The timer is **started** at tick `T` the first time a traffic event drives an
  allowance's traffic strictly above its throttle threshold while the timer is not
  already running. The surge window then covers ticks `T` through `T + grace`
  inclusive.
- While traffic stays above the throttle threshold, the timer keeps running across
  later ticks.
- **Expiry is inclusive at the far edge:** at any tick `now`, the window is
  still open when `now <= T + grace` and has expired when `now > T + grace`.
  So a traffic event at exactly `T + grace` is still within surge, and one at
  `T + grace + 1` is past it.
- If traffic drops back to `<= soft` (because a credit lowered it), the timer is
  **cancelled**: it stops running and no expiry is recorded.
- A later re-crossing above the throttle threshold **restarts a full new surge
  window** from the tick of the re-crossing. It does not resume a previous
  partially-elapsed window; the remaining time from any earlier window is
  discarded.

## Events

The traffic stream is processed in the order the lines appear. Each event line is

```
<tick> HAUL <truck> <hauls>
```

or

```
<tick> RETURN <truck> <hauls>
```

where `<tick>` is a non-negative integer, `<truck>` names a configured
truck, and `<hauls>` is a positive integer.

A `HAUL` requests `<hauls>` additional hauls for `<truck>`. The request also
counts against the truck's quarry, because every hauls the truck holds is
also held by its quarry. The traffic event is **all-or-nothing**: the full request
must be satisfiable, or the traffic event is denied and no counter, debt, or
reserve pool changes.

## Deciding a HAUL

For a `HAUL` of `n` hauls by a truck (and its quarry) at the event tick, the
engine determines how the request can be satisfied.

A **cap violation is absolute and checked first**: if adding `n` to the
truck's own traffic would exceed the truck cap the traffic event is denied
with `TRUCK_FULL`; otherwise if adding `n` to the quarry's traffic would exceed the
quarry cap it is denied with `QUARRY_FULL`. The truck check precedes the quarry
check.

Otherwise the engine works out how much of the request can be granted
**normally**, that is charged directly against the truck and quarry traffic
counters. The normal ceiling for an allowance is its cap while the allowance is
under the throttle threshold or within an open surge window, and its throttle
threshold once the allowance is over the throttle threshold with its surge
expired. The amount that can be granted normally is `n` capped by how far each
of the two allowances is below its own normal ceiling, taking the smaller of the
two. A normal grant that drives an allowance strictly above its throttle
threshold starts that allowance's surge window exactly as described above.

## Shared quarry reserve pool

When the normal grant cannot cover the full request, because the binding
throttle-or-surge ceiling is reached, the leftover shortfall is **borrowed**
from the quarry's shared reserve pool rather than denied, provided the pool has at
least that many hauls free. Borrowed hauls are an accommodation drawn from a separate
pool: they satisfy the traffic event but are **not** added to the truck or
quarry traffic counters, so they never push traffic above any cap and they do **not**
start a surge timer. The borrowed amount is recorded as that truck's
outstanding **debt** against the reserve pool and the pool's free capacity drops
by the same amount. Because the traffic event is all-or-nothing, a shortfall the
free pool cannot fully cover means the whole traffic event is denied with
`RESERVE_EMPTY` and nothing changes.

A `RETURN` releasing `<hauls>` hauls for a truck is processed in a fixed order:
the credited hauls **first repay that truck's own outstanding pool debt**,
returning hauls to the shared reserve pool, and only the remainder left after the
debt is settled reduces the truck's own traffic (and its quarry's). Repayment
unwinds the truck's borrows **newest first**, so the most recently borrowed
amount is repaid before older ones, until either the credited hauls are exhausted
or the truck's debt reaches zero. Because every event names a single
truck and is applied in stream order, the repayment of a contended pool and
any later traffic event that the freed-up pool enables are fully determined by
that order. A credit never drives a traffic counter below `0`; once any debt is
settled, crediting more than the truck's own traffic clamps that traffic at
`0`. A credit that leaves traffic back at or under the throttle threshold cancels
a running surge timer for that allowance.

## Output records and ordering

For each event the engine processes, it emits records in this canonical order.

A `RETURN` emits a single `<tick> REPAY <truck> <n>` line when, and only
when, it repays `n > 0` hauls of pool debt (`n` is the total repaid by that
credit); beyond that a `RETURN` produces no output.

A `HAUL` emits its **verdict line** first, either `<tick> PERMITTED`, or
`<tick> DENY <REASON>` where the reason is one of `TRUCK_FULL`, `QUARRY_FULL`, or
`RESERVE_EMPTY`. When allowed, the verdict line is followed by any surge-state
transition lines this traffic event caused, the **truck transition before
the quarry transition**, each being `<tick> SURGE_START <TRUCK|QUARRY> <name>` when a
window opens (or reopens) at this tick. If the traffic event drew on the reserve
pool, a final `<tick> DRAW <truck> <n>` line follows the transition
lines, where `n` is the borrowed amount. A `SURGE_START` is emitted only on a
transition from not-running to running (including a restart after a cancel);
staying over the throttle threshold across ticks does not re-emit it, and
borrowing from the reserve pool never emits one.

## Errors

If either input file cannot be read or parsed, references an unknown truck,
or violates the structural rules above (`hard < soft`, negative parameters, a
truck with no quarry, a non-positive `HAUL`/`RETURN` amount, a malformed
line), the engine writes a diagnostic to standard error and exits with a nonzero
status without printing a ledger.
