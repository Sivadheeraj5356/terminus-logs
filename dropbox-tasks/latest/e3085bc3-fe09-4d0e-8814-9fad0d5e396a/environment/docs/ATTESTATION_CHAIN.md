# Attestation chain

The replay worker derives `set_id` as an FNV-1a digest over the workload read
paths in job order. The same `set_id` value is copied into
`output/read_traces.json`, `output/measure_log.json`, and
`output/integrity_report.json`.

Digest rows in the measure log are keyed by the path string recorded for each
read in the trace. Manifest lookups for appraisal fields use the canonical path
form defined in `MODEL.md`.

The reconcile pass must agree with the replay worker on band selection, verb
dispatch, digest presence, and manifest field choice for every read.
