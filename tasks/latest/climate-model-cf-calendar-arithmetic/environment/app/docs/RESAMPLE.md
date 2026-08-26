# Resample

`climconvert resample --in PATH --freq mon|sea|ann --out PATH [--cache-dir PATH]` aggregates observations into climatological bins.

Bins follow the dataset calendar (month, season, or year keys), not fixed Unix-day widths. Repeated runs with identical inputs and a valid cache produce identical outputs. Default cache directory: `/var/lib/climconvert/cache`.
