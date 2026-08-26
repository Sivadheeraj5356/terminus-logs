# Implement `SpectralAnalyzer#run!` to drive the full spectroscopy pipeline. It sh

Submission: `7dfe4024-4b20-4236-b7bd-d493d89eeffe`  
Slug: `implement-spectralanalyzer-run-to-drive-the-full-spectroscop`  
Latest archive: `7dfe4024-4b20-4236-b7bd-d493d89eeffe_submission_2026-07-10T08_51_17.791Z.zip`  
Revisions: 1

## Task summary

Implement `SpectralAnalyzer#run!` to drive the full spectroscopy pipeline. It should fetch simulation data from the API on port 3000, compute spectral metrics, and write the analysis artifacts described in `/app/docs/manual_workflow.md`. The sensor identifier is set in the Containerfile at `/app/Containerfile` as `SENSOR_ID`. Use its value (e.g., `ACCEL-001`) to construct output filenames. The JSON report written to `/app/output/{SENSOR_ID}_analysis.json` must contain a `sensorId` string field set to the SENSOR_ID value, numeric fields `sampleRateHz`, `durationSec`, `damping`, `naturalFreqHz`, `rmsEnergy`, and `dominantFrequencyHz`, a `numSamples` field whose value exactly equals `sampleRateHz * durationSec`, and an `apiMetadata` object containing the response from the `/metadata` endpoint.

Required artifacts include: `/app/docs/manual_workflow.md`, `/app/Containerfile`, `/app/output/{SENSOR_ID}_analysis.json`, `/app/output/{SENSOR_ID}_spectrum.csv`, `/app/output/manifest.txt`.

Author Anonymous tagged this **hard** scientific-computing task (ruby, typescript, signal-processing, fft, api).

Time estimates: expert ~90.0 min, junior ~180.0 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `7dfe4024-4b20-4236-b7bd-d493d89eeffe_submission_2026-07-10T08_51_17.791Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
