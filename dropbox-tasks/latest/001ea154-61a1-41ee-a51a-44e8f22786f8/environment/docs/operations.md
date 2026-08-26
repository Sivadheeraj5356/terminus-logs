# Stream ingest operations

The offline stack under `/app/environment` simulates a multi-member ingest group
reading fixed broker fixtures. Workload shapes live in
`/app/environment/data/workloads.json`. Cluster metadata is in
`/app/environment/configs/cluster.json`.

Reproduce / regenerate:

```
cd /app/environment && go run /app/environment/cmd/stream-bench --workloads /app/environment/data/workloads.json --cluster /app/environment/configs/cluster.json --report /app/ingest_recovery_report.json
```

Baseline operator notes from the last incident are in
`/app/environment/logs/incident-trace/`. Report field definitions and recovery
thresholds are in `/app/environment/data/report_contract.md`.

Hardware caps are fixed at two CPUs and 4 GiB RAM for this exercise; scale-out
is not an option. Recovery work must stay inside the Go sources under
`/app/environment`. Go module builds may use `GOCACHE` and `GOMODCACHE` under
`/tmp` when the default cache locations are not writable.
