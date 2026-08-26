Repair the `fusion` binary in `/app/cmd/fusion` to implement the contract in `/app/docs/auroral-lattice-contract.md`.

The repaired binary must support this invocation:
`fusion --telemetry-dir /app/telemetry --calibration-dir /app/calibration --probe /app/probe/driftprobe --probe-batch /app/telemetry/public.cfr --out /app/output/events.tsv --audit-out /app/output/audit.json`

The binary must discover and rank calibration manifests using the configured probe, select the compatible manifest ensemble described by the contract, and reject malformed probe output or incompatible calibration data with a non-zero exit status.

The binary must decode all supported telemetry containers in deterministic directory order, validate container integrity before producing results, and implement the documented telemetry transformations exactly enough for all frame values, quality masks, batch names, and minute values to match the contract.

For each decoded frame, the binary must apply the selected manifest feature mapping, quality handling, clipping, centering, batch statistics, class scoring terms, and deterministic class tie-breaking specified in the contract. Event margins must use the documented fixed-point normalization and rounding.

The event output must be a TSV sorted by frame id with header `frame_id	batch	minute	zone	event	margin_milli`. The audit output must include the selected manifests, decoded row totals, per-batch statistics, and the SHA-256 digest of the exact event TSV bytes. Any malformed telemetry, probe, scoring, or I/O failure must exit non-zero and leave existing output files untouched; final outputs may be replaced only after both new payloads have been written successfully.
