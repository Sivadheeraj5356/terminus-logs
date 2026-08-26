# Retention attestation contract

The command accepts `--emit-attestation OUTPUT`, `--input-root ROOT`,
`--holdout RUN`, and `--coverage TARGET`.

`ra_run` reads a recursive tree of `.cell` files. A file contains `CELL/3`,
then `run_id=<id>`, then CSV with the exact header
`observation_id,peptide,retention_time,confidence`. Identifiers and peptides are
nonempty. Retention times are finite. Confidence is finite and in the closed
interval from zero to one. At least two runs and one observation are required.

An observation identifier is global to the selected tree. Repeated records with
the same identifier collapse only when run, peptide, retention time, and
confidence are all equal. Any conflict rejects the complete invocation.
Directory order, file names, file boundaries, and row order have no semantic
meaning. Source records still report each relative path, exact byte length,
row count, and lowercase SHA-256.

## Coordinates and models

Within each run, sort accepted observations by numeric retention time. Assign
the zero-based rank divided by `n-1`. A tie receives the arithmetic mean of the
positions occupied by the tied values before division. A singleton receives
`0.5`. This is a midrank coordinate and is unchanged by any positive affine
transformation applied to every retention time in one run.

A model center for a peptide is the ordinary median of all coordinates for
that peptide in the selected training runs. For an even number of coordinates,
the median is the arithmetic mean of the two middle values. Support is the
number of coordinates used. Model and run identifiers are sorted
lexicographically.

Every default replay holds out one run and fits from all other runs. No value
from the held-out run may contribute to its model or calibration residuals.
`--holdout R` emits only R's replay and fits the top-level model from that same
training selection. Its replay object must equal R's object from a default
invocation over the same inputs and target. Every held-out peptide must be
present in training data or the invocation fails.

Residual is `abs(coordinate - center)`. Calibration residuals come from the
selected training observations. Sort those residuals ascending and set
`k = ceil((m + 1) * TARGET)`, clamped to the integer interval `[1,m]`.
Threshold is sorted residual `k-1`. A held-out residual is covered exactly when
it is no greater than the threshold. Higher targets cannot lower the threshold.
The `quantile_rank` field equals `k`, and `coverage_target` equals the requested
target.

## JSON record

The top level has `schema_version`, `coverage_target`, `sources`,
`observations`, `runs`, `model`, `replays`, `lineage`, and `seal`.
The `schema_version` field equals `retention-attestation/3`. The `sources` field
reports file provenance, while `observations` reports the deduplicated semantic
rows. The `replays` field reports the requested held-out evaluations.

Observation records expose `observation_id`, `run_id`, `peptide`, `confidence`,
and `coordinate`. Run records expose `run_id`, sorted `observation_ids`, and
`coordinate_digest`. Models expose sorted `training_runs` and sorted `centers`;
each center has `peptide`, `center`, and `support`.
For these records, `run_id` means the acquisition run, `observation_ids` equals
the sorted membership of that run, `training_runs` means the selected model
scope, `centers` reports the peptide summaries, and `support` equals the number
of selected coordinates used for a center.

Replay records expose `holdout_run`, sorted `training_runs`, `model`,
`residuals`, `threshold`, `quantile_rank`, `covered`, and `total`. Residual
records expose `observation_id`, `peptide`, `coordinate`, `center`, `residual`,
and `covered`. `covered` equals the count of covered residual records and
`total` equals their count.
The `holdout_run` field means the excluded run for that replay.

Lineage has `selected_views` and `cache_entries`. Each selected view names the
holdout, its sorted training runs, and exactly the sorted observation
identifiers selected for training. Each cache entry exposes `scope`, `peptide`,
and `center`; scope must distinguish the complete sorted training-run
selection. Evaluation order must not change any replay or lineage record.

## Canonical closure and publication

Before sealing, sort every set-like array by the keys above. Remove `seal` and
serialize the complete remaining top-level object as compact JSON with
lexicographically sorted object keys and no insignificant whitespace. The
lowercase SHA-256 of those UTF-8 bytes is `seal.digest`;
`seal.algorithm` is `sha256`. Every semantic section is therefore bound. The
image provides `sha256sum` for independent checks of this byte stream.

Successful output is compact JSON plus one LF and is atomically renamed into
place. Any malformed input, conflict, missing or unknown argument, unknown
holdout, invalid coverage target, empty tree, or semantic failure returns
nonzero without changing an existing output. Repeating A, then another valid
input B, then A again produces byte-identical A output.
