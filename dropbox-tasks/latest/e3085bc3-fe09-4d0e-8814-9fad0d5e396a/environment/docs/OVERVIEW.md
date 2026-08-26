# Overview

Three stages run in sequence:

1. **Loader** (`cmd/loader`) lowers `data/policy.json` into `output/program.json`
   and writes a flat jobs file from `data/workload.json`.
2. **Hook** (`hook/`) replays jobs, writes `output/read_traces.json` and
   `output/measure_log.json`.
3. **Reconcile** (`cmd/reconcile`) compares traces, the digest log, and
   `data/manifest.json` into `output/integrity_report.json`.

Rebuild with `bash scripts/build.sh`.
