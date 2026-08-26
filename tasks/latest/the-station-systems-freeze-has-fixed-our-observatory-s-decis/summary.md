# The Station Systems Freeze has fixed our observatory's decision record, and the

- **UUID:** `53cba4ce-e6b5-4364-a7ef-77064ef0c814`
- **Slug:** `the-station-systems-freeze-has-fixed-our-observatory-s-decis`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The Station Systems Freeze has fixed our observatory's decision record, and the spectral analysis host is due for its audit. The Java estimator under /app/service produces the station's FFT band-power spectra for the geomagnetic channels; its working tree, however, no longer reflects the record: the build manifest resolves against artifact versions whose approvals are not in force, request values reach the telemetry store as concatenated statement text contrary to station policy, and the estimator computes to a spectral methods revision that no longer governs.

Restore the host to the decision record as of the freeze:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
