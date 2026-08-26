# Capture store layout

`pendulum_captures.duckdb` holds the input tables `jobs` and `frame_strips`. Output
tables `recovered_series`, `fit_results`, and `recovery_edges` are created by the motion
solver at run time. Column contracts are documented in `/app/schema.sql`.

A pristine copy of the seeded store is restored at verification time from
`/opt/seed/pendulum_captures.duckdb`. Verification uses pytest with `--ctrf` reporting.
