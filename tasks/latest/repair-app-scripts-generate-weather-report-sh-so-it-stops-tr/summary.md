# Repair /app/scripts/generate_weather_report.sh so it stops trusting the stale st

- **UUID:** `61c7240f-18f5-4ad9-a350-2ff3292e60eb`
- **Slug:** `repair-app-scripts-generate-weather-report-sh-so-it-stops-tr`
- **Category:** data-processing
- **Difficulty:** hard

## Summary

Repair /app/scripts/generate_weather_report.sh so it stops trusting the stale station cache and rebuilds the weather evidence from /app/data/station-readings.csv, /app/metadata/station-aliases.csv, /app/metadata/sensor-health.csv, and the bundled NOAA-style fixtures in /app/metadata/noaa-station-fixtures. It should not use the network, and rerunning it from a clean /app/output directory should produce byte-identical JSON.

Write the output files described in /app/docs/weather-evidence-contract.md; read that file carefully for exact fields, types, sort orders, and rounding rules. The outputs are /app/output/weather-evidence.json, /app/output/noaa-stations.json, /app/output/review-queue.json, /app/output/station-day-rollups.json, /app/output/excluded-readings.json, /app/output/station-trend-alerts.json, and /app/output/station-health-summary.json.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
