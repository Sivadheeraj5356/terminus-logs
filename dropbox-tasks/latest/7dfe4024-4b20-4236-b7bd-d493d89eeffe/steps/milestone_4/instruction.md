The spectroscopy pipeline needs validation and diagnostics. Add a `validate_config` method to `SpectralAnalyzer` that checks all configuration parameters are within physically plausible ranges — sample rate between 100–10000 Hz, duration between 0.1–60 seconds, damping between 0–1, natural frequency between 1–1000 Hz. Sensor IDs must match the pattern `ACCEL-` followed by three digits. Return a hash with `valid` (boolean) and `errors` (array) keys.

Include a **cross-parameter** Nyquist constraint: the natural frequency must not exceed half the sample rate (`natural_frequency_hz <= sensor_frequency_hz / 2`). Violating the Nyquist-Shannon sampling theorem would cause aliasing in the acquired signal.

Add a `generate_debug_report` method that produces a JSON report at `/app/debug_report.json` when the API returns unexpected data. The report should include the experiment parameters (`parameters`), the full validation result (`validation` with `valid` and `errors` keys), and a `timestamp`.

Document all range constraints and the Nyquist criterion in `/app/docs/validation_spec.md`.