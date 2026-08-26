ramp operations notes

the apron team posts one record per jet bridge cycle. a cycle is the use of a passenger boarding bridge by a single arrival or departure. each record carries cycle_id, carrier_iata, gate_zone, body_code, mtow_tons, gate_assigned_ts (when ramp control assigned the bridge), actual_inblock_ts (when the bridge actually docked or undocked), dwell_minutes, status, and movement.

input lives under ramplog as ndjson files split by day plus a separate anomalies file that holds late-arriving corrections. the same cycle_id can appear in more than one file when ops files a follow-up record. read every ndjson under ramplog before deciding what a cycle's final shape looks like.

the goal is to write a per-cycle billing line to output/cycles.ndjson and a per-carrier per-verdict aggregate to output/summary.toml. both go through the same sort and digest discipline so digest.txt is byte for byte reproducible.

run the binary by building from /app/jetway then invoking it. the parser reads /app from the working tree by default. set AIRBRIDGE_DATA to override the input root and AIRBRIDGE_OUT to override the output directory.

the rule book is split between gate_handbook and the codex folder. keep reading.
