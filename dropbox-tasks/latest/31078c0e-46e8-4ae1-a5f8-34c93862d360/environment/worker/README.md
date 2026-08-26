# OCI diffusion card worker

Run the report generator with:

```bash
npm run report -- --spec-dir /app/worker/fixtures/specs --calibration /app/worker/fixtures/calibrations.json --output /app/output/diffusion-report.json
```

The cards intentionally mix JSON and a small YAML shape used by the release lab. The worker is expected to simulate cards, reduce duplicate image/calibration cohorts, and write the deterministic report described in the task prompt.
