# Cryostat boil-off warden — behavior reference

This document specifies the exact semantics `/app/cryoctl` must reproduce. It is
the authoritative reference for the warden's behavior.

## Invocation and I/O

The binary reads one JSON object from stdin:

```
{"grace": <int G>, "events": [ {"type": <str>, "cryostat": <str>, "t": <int>}, ... ]}
```

`G` is the grace allowance in seconds (a non-negative integer): the tolerated
amount of above-relief dwell before a boil-off interval starts being charged. `t`
is an integer epoch second. Events are already in non-decreasing `t` order and are
processed in the order given. It writes one JSON object to stdout:

```
{"audit": [ ... ], "boiloff": [ ... ], "cryostats": { ... }}
```

## Audit

`audit` has one entry per input event, in input order. Each entry is
`{"index", "type", "cryostat", "t", "status"}` where `index` is the event's
zero-based position, `type`/`cryostat`/`t` echo the input, and `status` is
`"accepted"` for a recognized `type` (`press_high`, `press_low`, `purge_on`,
`purge_off`, `report`) or `"rejected"` for any other `type`. A rejected event has
no effect on state, and processing continues with the next event.

## Cryostat state and transfer-line purge windows

Each cryostat is tracked independently. A cryostat starts **settled** (at or below
the relief threshold, not dwelling above it).

- `press_high` puts the cryostat into the **at-risk** state: head pressure has
  risen above the relief threshold and now dwells above it continuously, so liquid
  helium is boiling off. This is tolerated only for the grace allowance before an
  interval is charged. A `press_high` for a cryostat that is already at risk has no
  effect.
- `press_low` returns the cryostat to the **settled** state (above-relief dwelling
  stops). A `press_low` for a cryostat that is already settled has no effect.
- `purge_on` opens a transfer-line purge window for the cryostat; `purge_off`
  closes it. While a purge window is open the cryostat's boil-off allowance clock
  is **frozen**: see "Active time" below. Purge state is independent of pressure
  state — a purge window may open or close whether the cryostat is at risk or
  settled. The purge is a single open/closed condition, not a nesting depth: a
  `purge_on` while a window is already open, or a `purge_off` while none is open,
  has no effect.

## Active time

The **active time** that elapses for a cryostat over any wall-clock span is the
portion of that span during which the cryostat is **not** in a transfer-line purge
window. Time spent inside a purge window is frozen and does not count as active
time. The grace allowance and the `exposed` total are both measured in active time.

A cryostat's `exposed` is the total active time the cryostat spends in the
**at-risk** state, accumulated across the whole run.

## The grace allowance and boil-off intervals

While a cryostat is at risk, active time accrues against the allowance `G`. The
above-relief dwell is tolerated for its first `G` seconds of active time; a
**boil-off interval** is the part of a continuous at-risk stretch that extends
beyond that allowance.

- The interval's **start** is the wall-clock instant at which `G` seconds of active
  time have accumulated since the `press_high`. Because active time is frozen
  during a purge window, this instant is computed: it is `G` active seconds after
  the `press_high`, with any frozen (purge) time added back so the start is
  expressed in wall-clock time. The start does **not** coincide with the
  `press_high` event unless `G` is zero and no purge window intervened. This start
  is a computed boundary, not an event; when an explicit event occurs at the exact
  instant that boundary falls, the event's effect on the cryostat's state governs
  first, and whether (and when) the boil-off interval opens is decided from the
  resulting state.
- The interval's **end** is the wall-clock instant at which the cryostat settles
  (`press_low`), or, if the cryostat is still at risk, the wall-clock instant of the
  next `report` event for that cryostat. A cryostat still at risk with no `report`
  contributes no closed boil-off interval.
- When a purge window is open, the allowance timer is paused and resumes — it does
  not restart — when the window closes. An at-risk stretch is a single continuous
  span from the `press_high` until the matching `press_low` (or `report`)
  regardless of any purge windows within it; the allowance is consumed once across
  that whole span, in active time.

The allowance resets only when the cryostat settles. A new `press_high` after a
`press_low` begins a fresh at-risk stretch with the full allowance `G`.

## Boil-off output and zero-length suppression

Each closed boil-off interval is emitted in `boiloff` as `{"cryostat", "start",
"end"}` with `start` and `end` as wall-clock epoch seconds. An interval whose
computed `start` equals its `end` is **zero-length** and is **omitted** from the
output (an at-risk stretch that never accumulates more than `G` active seconds
before it ends produces no boil-off interval).

`boiloff` is sorted by `cryostat`, then by `start`, then by `end`. The `cryostats`
map is keyed by cryostat name in sorted order, each value `{"exposed": <int>}`.

## Worked examples

With `G = 30`:

- `press_high`@100, `press_low`@200 (no purge): the allowance is consumed over
  `[100,130)`, the boil-off interval is `[130, 200]`, and `exposed` is `100`.
- `press_high`@100, `press_low`@120: only 20 active seconds of above-relief dwell
  elapse, which is below `G`, so there is no boil-off interval; `exposed` is `20`.
- `press_high`@100, `report`@300: the cryostat is still at risk at the horizon, so
  the boil-off interval `[130, 300]` is closed at the report; `exposed` is `200`.
- `press_high`@100, `press_low`@130: `G` active seconds accrue exactly at wall 130,
  which is where the boil-off start would fall — but a `press_low` occurs at that
  same instant. Because the interval start is a computed boundary rather than an
  event, the coincident `press_low`'s effect on the cryostat's state is applied
  first: the cryostat settles at 130, so the interval that would have opened at 130
  ends at 130, is zero-length, and is suppressed. There is no boil-off interval;
  `exposed` is `30`. Any explicit event landing exactly on the computed boundary is
  resolved the same way — the event updates the cryostat's state first, and whether
  (and when) the interval opens follows from that resulting state.
