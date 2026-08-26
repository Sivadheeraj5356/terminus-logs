`/app/bin/windowjudge.js` replays one recorded HSM ceremony stream. It reads one JSON document on stdin and writes exactly `{"intervals":[...]}` on stdout. Each interval has `start`, `end`, `reason`, and exactly one actor field, `key`, `package`, `sensor`, or `player`; if no windows are confirmed, `intervals` is an empty array.

The input has `until`, `events`, and exactly one top-level mode array: `keys`, `packages`, `sensors`, or `players`. Rows are half-open, open rows close at `until`, and output rows are sorted by actor value and then numeric `start`.

Implement the four ceremony-window modes described in `/app/docs/ceremony-windows.md`: key compromise, package admission, sensor hysteresis, and player flag-fall windows. That document is the contract for the field schema, deferred-boundary timing, suspension windows, replacement behavior, sensor hold handling, player pause/recovery behavior, and reason strings.
