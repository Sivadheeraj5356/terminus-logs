# Repair /app/scripts/generate_weather_report.sh so it stops trusting the stale st

Submission: `61c7240f-18f5-4ad9-a350-2ff3292e60eb`  
Slug: `repair-app-scripts-generate-weather-report-sh-so-it-stops-tr`  
Latest archive: `61c7240f-18f5-4ad9-a350-2ff3292e60eb_submission_2026-07-09T17_00_18.318Z.zip`  
Revisions in Dropbox: 4

## Task summary

Repair /app/scripts/generate_weather_report.sh so it stops trusting the stale station cache and rebuilds the weather evidence from /app/data/station-readings.csv, /app/metadata/station-aliases.csv, /app/metadata/sensor-health.csv, and the bundled NOAA-style fixtures in /app/metadata/noaa-station-fixtures. It should not use the network, and rerunning it from a clean /app/output directory should produce byte-identical JSON. Write the output files described in /app/docs/weather-evidence-contract.md; read that file carefully for exact fields, types, sort orders, and rounding rules. The outputs are /app/output/weather-evidence.json, /app/output/noaa-stations.json, /app/output/review-queue.json, /app/output/station-day-rollups.json, /app/output/excluded-readings.json, /app/output/station-trend-alerts.json, and /app/output/station-health-summary.json. Canonicalize station IDs before doing anything else, exclude blank temperatures, maintenance holds, and offline sensor-window readings before duplicate checks, keep the highest ingest_sequence for each station and UTC instant, and treat bad or mismatched station fixtures as missing metadata. The top-level weather evidence object should have readings_count, station_count, missing_station_count, duplicate_reading_count, excluded_reading_count, sensor_blackout_count, and stations; stations is an array of station objects sorted by station_id.

Required artifacts include: `/app/scripts/generate_weather_report.sh`, `/app/data/station-readings.csv`, `/app/metadata/station-aliases.csv`, `/app/metadata/sensor-health.csv`, `/app/metadata/noaa-station-fixtures`, `/app/output`, `/app/docs/weather-evidence-contract.md`, `/app/output/weather-evidence.json`.

Author anonymous tagged this **hard** data-processing task (noaa, metadata, csv, json, jq, bash).

Time estimates: expert ~60 min, junior ~120 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `61c7240f-18f5-4ad9-a350-2ff3292e60eb_submission_2026-07-09T17_00_18.318Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
