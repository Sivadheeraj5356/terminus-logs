# Resolved artifacts

resolve-precedence output:
- expedition_id
- reports (winning reports only, sorted by report_id)
- replay_seq (always 1)
- lane_bind

lane_bind follows BIND_CRC.md lane_bind section. Sort winning report_id values ascending, join with semicolons, then append a trailing semicolon. Example bind string before CRC: nt-003;sr-002;

Mirrors to /app/state/{expedition_id}-resolved.json

export-atlas reads this on-disk resolved snapshot for dive_lanes. The reconciled observations file alone is not sufficient for lane winners.

reconcile-observations validates replay_seq equals 1 per REPLAY_COUNTER.md before linking observations.
