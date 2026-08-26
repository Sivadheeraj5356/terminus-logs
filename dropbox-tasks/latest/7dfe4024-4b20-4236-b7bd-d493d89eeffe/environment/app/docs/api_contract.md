# Sensor Simulation API Contract

## Base URL

`http://localhost:3000`

## Endpoints

### GET /health

Returns service status.

Response: `{"status": "ok"}`

### GET /metadata

Returns API and simulator metadata.

Response fields:
- `apiVersion` — version string
- `simulator` — simulator module name
- `supportedUnits` — physical units for output
- `fftMethod` — FFT computation method
- `maxSamples` — maximum sample count per simulation

### POST /simulate

Generates a damped harmonic oscillator response.

Request body:
- `sampleRateHz` (number) — ADC sample rate in Hz
- `durationSec` (number) — capture window in seconds
- `damping` (number) — dimensionless damping ratio
- `naturalFreqHz` (number) — undamped natural frequency in Hz

Response:
- `sensorId` — sensor identifier string
- `samples` — array of floating-point acceleration values
- `fftBins` — array of `{frequencyHz, magnitude}` objects
- `sampleRateHz` — echo of the request parameter
- `durationSec` — echo of the request parameter

### Error responses

All endpoints return 400 with `{"error": "message"}` on malformed input.
