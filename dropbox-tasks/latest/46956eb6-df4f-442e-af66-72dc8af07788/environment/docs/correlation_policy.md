# Correlation window policy

Incident correlation pairs each restart marker with error events for the same PID. A **correlated triple** exists when an error timestamp `E` and restart timestamp `R` satisfy `E <= R` and `R - E <= window_ns`. Implementations must use this subtraction form (after checking `E <= R`) so timestamps near `UINT64_MAX` cannot wrap.

The nanosecond window is not hard-coded in the replayer sources. `/app/config/replayer.toml` supplies:

- `correlation_window_ns_default` — fallback when a scenario has no override (currently `60000000000`)
- `[scenarios.<id>]` sections with `correlation_window_ns` per pack scenario id (for example `lane_delta` uses `30000000000` and `lane_epsilon` uses `45000000000`)

The matrix driver passes each pack `--scenario` id to `telreplay`; the replayer reloads the config file on startup and must apply the resolved window when counting triples and affected PIDs. Changing a scenario override in the config file changes correlation results on the next run without rebuilding the binary.
