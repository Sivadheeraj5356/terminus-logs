# Cedar Fork channel hydrograph contract

## Purpose

Report Muskingum-routed peak discharge (m³/s), time-to-peak (h), and outflow hydrographs (m³/s) for each admitted channel reach on every flood event carried in a field-survey fixture.

## Field-survey fixture (binary)

A survey is a little-endian binary blob. All integers are unsigned; all discharges, storage times, and stationing are IEEE-754 double precision (8 bytes). Strings are ASCII with a one-byte length prefix. Fields appear in this order:

```
magic          4 bytes, the ASCII "CFR1"
dt_hours       f64            routing step length in hours
peak_min_cms   f64            admission floor on the rounded peak outflow (m³/s)
n_reaches      u16            reach count
reach[n_reaches]:
    id_len     u8             length of reach_id
    reach_id   id_len bytes   ASCII identifier
    river_km   f64            channel stationing (km)
    K          f64            storage time parameter (hours)
    X          f64            dimensionless storage weighting in [0, 0.5]
    n_up       u8             number of upstream feeder reaches
    upstream[n_up]:
        up_len u8             length of the upstream reach_id
        up_id  up_len bytes   ASCII identifier of a feeder reach
n_events       u16            event count
event[n_events]:
    name_len   u8             length of the event id
    name       name_len bytes ASCII event id
    n_steps    u16            number of routing steps
    headwater  f64 * n_steps  upstream boundary inflow marks (m³/s)
    n_lat      u8             number of lateral mark blocks
    lateral[n_lat]:
        rid_len u8            length of the reach_id the marks belong to
        rid     rid_len bytes ASCII reach_id
        marks   f64 * n_steps lateral inflow marks (m³/s)
```

Every headwater reach (empty `upstream`) receives the same headwater series as its boundary inflow. A reach with no lateral block carries no lateral marks.

## Muskingum recurrence and weights

A storage pass maps an effective inflow series I[t] to an outflow series O[t]:

```
O[t] = C0·I[t] + C1·I[t−1] + C2·O[t−1]
```

For a storage time κ (hours), weighting X, and step `dt_hours`, the weights are

```
D  = κ·(1 − X) + 0.5·dt_hours
C0 = (0.5·dt_hours − κ·X) / D
C1 = (0.5·dt_hours + κ·X) / D
C2 = (κ·(1 − X) − 0.5·dt_hours) / D
```

so that C0 + C1 + C2 = 1. The first outflow value seeds the pass from the first effective inflow value.

A reach may be advanced through more than one storage pass in series; the number of passes for each reach, and the storage time used per pass, follow from `K`, `X`, and `dt_hours` as fixed by the calibration cases.

## Rounding

Every discharge written into an outflow series - peaks, time-to-peak, and each O[t] - uses round-half-even at three decimal places. A rounded outflow value is the value reused everywhere downstream: by the next storage pass, by the next timestep, and by any reach fed from it.

## Effective inflow

Each reach forms its effective inflow from three sources: its own headwater boundary series (headwater reaches only), the routed outflow arriving from its upstream reaches, and its lateral marks. The timing with which the upstream outflow and the lateral marks enter a reach's effective inflow is fixed by the calibration cases.

## Reach admission

A reach is admitted for an event when its rounded peak outflow meets the survey `peak_min_cms`; the exact floor boundary is fixed by the calibration cases. A reach that is not admitted is omitted from the output; how a non-admitted reach affects the reaches below it is fixed by the calibration cases.

## Reported quantities

The calculator prints one JSON object to standard output, matching `/app/config/channel_quantities.schema.json`:

```
{
  "<event_id>": [
    {
      "reach_id": "<id>",
      "peak_cms": <number>,
      "time_to_peak_h": <number>,
      "outflow_cms": [<number>, ...]
    },
    ...
  ],
  ...
}
```

- Object keys are the event ids carried in the survey, sorted lexicographically.
- Inside each event, admitted reaches appear sorted by ascending `reach_id`.
- `outflow_cms` length matches the event step count.
- `peak_cms` is the maximum rounded outflow value of the reach.
- `time_to_peak_h` is (index of the first maximum outflow value) × `dt_hours`, then half-even rounded to three decimals.

A single-event calibration survey prints one event object whose value is the reach array for that event.

## Calibration catalog

Each folder under `/app/calibration/` ships one worked survey (`survey.bin`, one event named `event`) together with its measured target quantities in `calibration.json`. case_01 is a single-reach baseline. case_02 and case_03 are single reaches with larger storage times. case_04 places lateral marks on a single reach. case_05 and case_06 are two- and three-reach cascades with no laterals. case_07 sits exactly on the peak floor; case_08 falls just under it. case_09 loses an upstream reach to the floor while a downstream reach carries its own lateral marks. case_10 places lateral marks on a downstream reach. case_11 ties two headwaters at equal `river_km` into one reach. case_12 uses `dt_hours = 2` with two reaches.

## Field calculator invocation

```
/app/bin/channel-route <survey.bin>
```
