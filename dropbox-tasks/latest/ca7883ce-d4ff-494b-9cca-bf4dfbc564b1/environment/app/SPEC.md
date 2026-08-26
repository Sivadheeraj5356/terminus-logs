The trace is a whitespace-separated command file. Strip text after `#` and ignore blank lines.

Commands are `OBS id start end value zone rev`, `CORRECT id start end value zone rev`, `SNAP t`, `VACUUM cutoff`, and `REVOKE id rev`. A record is valid only when `end > start`, `value > 0`, and `rev >= 0`. `OBS` creates or replaces an id only when the id is missing or the new revision is at least the live revision. `CORRECT` only updates an existing id under the same revision rule. `REVOKE` removes an existing id only when its revision is at least the live revision. `VACUUM` removes every live record with `end <= cutoff`, sorted by id for event order.

`SNAP t` appends a snapshot entry `t|zone_load` where `zone_load` sums values for records with `start <= t < end`, sorted lexicographically by zone as `zone:value` pairs joined by semicolons or `-` when empty. The final `active_records` field is sorted by id as `id:start:end:value:zone:rev`; final `zone_load` uses all live records; `snapshots` joins snapshot entries with semicolons or uses `-`.

Print exactly `active_records`, `zone_load`, `snapshots`, `obs_count`, `correction_count`, `snap_count`, `vacuum_count`, `revoke_count`, `latest_rev_sum`, `trace_hash` in that order, one `key=value` row per field and no extra output.

The hash feeds those nine pre-hash audit values followed by accepted events in trace-processing order. Event strings are lowercase and colon-delimited:
`obs:id:start:end:value:zone:rev` for accepted `OBS`;
`correct:id:start:end:value:zone:rev` for accepted `CORRECT`;
`snap:t:zone_load` for every accepted `SNAP`, where `zone_load` is the same string used in the corresponding snapshot entry;
`vacuum:id:end` once per record removed by `VACUUM`, with removed records processed in sorted id order;
and `revoke:id:requested_rev:old_rev` for accepted `REVOKE`. Rejected commands append no event. Hash arithmetic uses UTF-8 bytes, `h=(h*137+byte) mod 1000000007`, and delimiter byte 31 after each value or event.
