# Reconstruction energy and noise audit

## Denoised traces

After inverse Haar reconstruction and padding trim, emit `/app/output/denoised-traces.json` with:

- `schema_version` = 1
- `policy_revision_id` matching the active threshold policy
- `effective_levels` matching the clamped level count
- `traces`: array of `{trace_id, samples}` in ascending `trace_id` order
- `content_sha256`: hex SHA-256 of the canonical JSON body of the traces array alone (compact keys sorted per object as produced by the staging writer for that array payload)

Samples are written with 12 decimal places of rounding for determinism.

## Residual energy

For each trace with original samples `x` and denoised samples `y` of equal length:

- `signal_energy = sum_i x_i^2`
- `residual_energy = sum_i (x_i - y_i)^2`
- `relative_residual = residual_energy / max(signal_energy, 1e-18)`

Aggregate fields in `/app/output/noise-audit.json`:

- `schema_version` = 1
- `policy_revision_id`
- `mad_sigma` from the journal
- `total_signal_energy` sum over traces
- `total_residual_energy` sum over traces
- `mean_relative_residual` mean of per-trace `relative_residual`
- `trace_audits`: per-trace `{trace_id, signal_energy, residual_energy, relative_residual}` sorted by `trace_id`
- `content_sha256` of the denoised-traces file bytes as written on disk

## Energy certification

Lab certification compares `total_residual_energy` and `mad_sigma` against the independent MAD and soft-threshold reconstruction. Export products must be derived from staged coefficient and journal artifacts, not by re-parsing raw traces to bypass the decompose stage.
