# Maintenance exclusions

Each maintenance_events row defines a blackout interval for tank_readings on the same tank_id.

A reading timestamp is excluded when it is greater than or equal to timestamp_start and strictly before timestamp_end. The end timestamp is not excluded (half-open interval).

Excluded readings must not affect heat leak integration or derived boil-off rates.

Maintenance event_type values are informational only; all maintenance rows apply the same exclusion rule.
