# coverd

A safety analyzer for counter systems — resource pools, work queues,
replication token schemes — used to check whether a system can ever
accumulate a given combination of amounts at once. It reads one job as JSON
on stdin and writes the per-query verdicts as JSON on stdout.

## Run

```
cd /app && go build
go run . < /app/samples/producer.job.json
```

Each `*.job.json` under `/app/samples/` is a complete stdin payload; the
matching `*.expected.json` holds the verdicts the job must produce.

## Layout

- `main.go` — stdin/stdout plumbing.
- `model/` — the job types.
- `analysis/` — the analyzer.
- `docs/` — the authoritative contract: `spec.md`, `output_schema.md`,
  `glossary.md`.
- `samples/` — worked jobs with expected verdicts.
