# Incident notes (internal)

Symptoms from the last shift:

- CPU stayed flat while ingest lag grew after a workload shape change.
- Operators edited cluster metadata without recovering the offline report.
- Report schema and digest formatting still look fine. Per-scenario health
  thresholds do not.

Reliable facts:

- The simulator is deterministic for a given workload file.
- stream-bench loads `/app/environment/configs/cluster.json` at startup.
- The verifier deletes the report and rebuilds it from the Go tree.
- `tools/check_digest.py` is shared with the verifier; leave it alone.

Unreliable / historical:

- Notes from the fairness experiment conflict with recovery throughput targets.
- Cluster JSON fields such as `lane_scan`, `fetch_credit_mode`, and
  `mark_style` were added during the canary; the offline bench may not honor
  them the way ops expects.
