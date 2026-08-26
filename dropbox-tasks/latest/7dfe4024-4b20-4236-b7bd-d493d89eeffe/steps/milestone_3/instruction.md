Implement `SpectralAnalyzer#run!` to drive the full spectroscopy pipeline. It should fetch simulation data from the API on port 3000, compute spectral metrics, and write the analysis artifacts described in `/app/docs/manual_workflow.md`.

The sensor identifier is set in the Containerfile at `/app/Containerfile` as `SENSOR_ID`. Use its value (e.g., `ACCEL-001`) to construct output filenames. The JSON report written to `/app/output/{SENSOR_ID}_analysis.json` must contain a `sensorId` string field set to the SENSOR_ID value, numeric fields `sampleRateHz`, `durationSec`, `damping`, `naturalFreqHz`, `rmsEnergy`, and `dominantFrequencyHz`, a `numSamples` field whose value exactly equals `sampleRateHz * durationSec`, and an `apiMetadata` object containing the response from the `/metadata` endpoint.

The CSV spectrum at `/app/output/{SENSOR_ID}_spectrum.csv` must have the header `frequencyHz,magnitudeDB`.

After the pipeline completes, write a manifest at `/app/output/manifest.txt` listing the two output filenames, one per line.
