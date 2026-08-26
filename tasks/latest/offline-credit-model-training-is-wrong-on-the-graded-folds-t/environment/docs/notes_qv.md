# Watermark and frame notes

Late-arriving revisions can show an early `valid_from_ms` while their
`ingested_ms` sits past the sample horizon. Training materialization must keep
those revisions out of the chosen feature while still listing them in
`candidate_revs` when `valid_from_ms` is not after the effective sample time.

Feature packs arrive as `put` / `kill` frames under
`/app/environment/data/features/` (for example
`/app/environment/data/features/pk_w.json`). A `kill` frame marks an existing
revision revoked. Revoked revisions are never selectable.
