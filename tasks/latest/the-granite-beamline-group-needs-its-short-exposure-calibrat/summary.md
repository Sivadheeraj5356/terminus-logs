# The Granite beamline group needs its short-exposure calibration packet settled b

- **UUID:** `4b2e2aeb-b0c0-467e-adc9-f185b5a9a4ab`
- **Slug:** `the-granite-beamline-group-needs-its-short-exposure-calibrat`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The Granite beamline group needs its short-exposure calibration packet settled before the next horn run. The operations team needs a schedule that delivers the requested neutrino flux without exceeding horn temperature, transition-current, or shielding limits.

Build the local calculator in `/app/main.js`; `/app/task_file/beamline-tuner` is the command the control-room staff will use. The public laboratory protocol and score-sheet contract are at `/app/task_file/beamline_operations_protocol.txt`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
