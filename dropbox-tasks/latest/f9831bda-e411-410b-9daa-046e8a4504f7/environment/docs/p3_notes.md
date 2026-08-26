# Profile matrix notes

Profile ids lane_amber, lane_birch, lane_coral, and lane_drift map to schedule files p3/schedules/xa.json, p3/schedules/xb.json, p3/schedules/xc.json, and p3/schedules/xd.json under /app/environment/p3/schedules/. Each schedule sets cap_bytes for slab and pin packing under frame_unit and grant_unit.

Slab cache slots must invalidate when epoch_dn or epoch_stamp rotates across profiles. score_hex issuer bytes come from vendor mirror shard JSON referenced by shard_ref, not from schedule epoch_dn.

Mirror pairs are lease with lease_echo, worker with worker_echo, and bind with bind_echo. Log tails under /app/environment/fixtures/logs/ are investigative only and may omit fields present in schedules or shard fixtures.
