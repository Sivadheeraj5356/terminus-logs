Storage operators report that thin-provisioned volumes still show high utilization after trim replay exits zero. Guest trim logs discarded ranges, but chunk inventory exports show no reclaimable slot change. Array trim telemetry reports cleared extents while the volume free-map digest stays on a prior epoch.



A second replay window fails convergence: trim transcripts, digests, propagation traces, checkpoint persistence, and staging revision disagree. Resuming after interrupting the first window leaves staging revision lagging the digest epoch despite a zero exit. Convergence requires every export surface to agree.



Policy in `/app/environment/config/trim_policy.toml` and `/app/environment/docs/export_contract.md` defines intended bindings; the replay toolchain under `/app/environment` does not honor them. Repair the implementation so the normal pipeline regenerates compliant artifacts and rebuild `/app/bin/volutil`. Do not write static JSON to `/app/output` or patch only the replay shell script.



From `/app`, run `bash /app/environment/scripts/repro_trim_cycle.sh` (two windows). The replay writes `/app/output/trim_transcript.json`, `/app/output/slot_map_digest.json`, `/app/output/propagation_trace.jsonl`, and `/app/output/convergence_report.json`. Record schemas (including `peer_id`, `span_start`, `span_end`, `stride_units`, `lane_tick`, `body_hex`, `epoch`, `series_num`, `series_den`, `slots_free`, `applied_bytes`, `skipped_bytes`, `tick`, `a_val`, `b_val`, and `cycle`), ordinal-ladder rules, digest formula, resume/append semantics, and convergence invariants are in `/app/environment/docs/export_contract.md`. Resume with `/app/bin/volutil run /app/output`, `CYCLE`, and `APPEND_EXPORT=1` on retained output; idempotent append reruns and interrupted resume must match a fresh two-window run. `/app/bin/volutil try` exits zero only when exports align.

