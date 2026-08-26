# Source Estimates

Write `/app/output/events.json` as UTF-8 JSON:

```json
{
  "events": [
    {
      "event_id": "E01",
      "f0_hz": 0.0,
      "chirp_hz_per_s": 0.0,
      "start_s": 0.0,
      "end_s": 0.0,
      "relative_power": 0.0,
      "support": 0
    }
  ]
}
```

Also write `/app/output/recovered.sqlite` with a table named `events` containing
the same fields. `support` is the number of instrument-window spectral
detections used in the merged source estimate. Reported sources must have
positive `relative_power` and at least 4 supporting instrument-window
detections.

The two files should contain the same source estimates. In JSON, `event_id` is a
non-empty string, `support` is an integer, and the frequency, chirp, time, and
power fields are numbers.

`start_s` and `end_s` should describe the fitted activity interval for the
merged physical source. The measurements are finite survey windows, so boundary
estimates may be reported at the fitted source edge or at the edge of the
supporting survey-window span when the boundary is not directly observed. Do
not shrink the interval to only the highest-power core of the detection; include
low-power edge windows when their aliases are consistent with the same merged
source.
