# hopledger

Offline relay mesh hop accounting tool. The replay contract is documented under `/app/environment/docs/`.

Build:

```bash
go build -C /app/environment -o /app/environment/bin/hopledger .
```

Run:

```bash
/app/environment/bin/hopledger run \
  --manifest /app/environment/fixtures/manifest.json \
  --report /app/output/report.json \
  --digest /app/output/digest.txt \
  --audit /app/output/audit.jsonl
```
