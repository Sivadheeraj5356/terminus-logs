# Brownian diffusion checkpoint protocol

The harness reconstructs one three-dimensional Brownian-motion experiment and supports incremental laboratory acquisition. Build it with `/app/environment/build.sh` and invoke `/app/environment/run.sh` in one of these forms:

- `analyze --spec <definition> --state <checkpoint> --db <DuckDB file> --report <JSON file>`
- `resume --spec <definition> --state <checkpoint> --db <DuckDB file> --report <JSON file>`
- `rebuild --state <checkpoint> --db <DuckDB file> --report <JSON file>`

`--help` exits 0. A successful mode exits 0 and emits exactly the report file bytes to standard output. Invalid flags, invalid definitions, duplicate shard IDs, records outside shards, orphan shard terminators, or aliased output paths exit 2. Scientifically insufficient observations exit 3. A missing, malformed, tampered, noncanonical, or incompatible checkpoint exits 4. Output publication failure exits 5. Failure must not create or replace any requested checkpoint, database, or report artifact that existed before the command.

## Definition and shard recovery

The definition contains exactly one metadata line outside all shards and one or more shards. Metadata is `@@META|dt=<positive decimal>|dimensions=3|box=<positive decimal>|particles=<comma-separated unique IDs>|fit=<start>:<end>`. Particle IDs and shard IDs match `[A-Za-z0-9_.-]+`. At least two particles are required. `1 <= start < end`, and the recovered experiment must ultimately provide at least three fitted lags.

A shard begins with `@@SHARD|id=<ID>|generation=<nonnegative integer>` and ends at `@@END_SHARD`, the next shard, or end of file. Shard IDs are globally unique within a definition. A line beginning `R|` outside a shard is invalid input. Other nonprotocol lines are ignored.

A data line is `R|tick|particle|x|y|z|crc32`. `tick` is a nonnegative integer. Coordinates are finite decimals in `[0, box)`. `crc32` is eight lowercase hexadecimal digits equal to CRC-32 of the UTF-8 bytes `tick|particle|x|y|z`, preserving the original five text tokens. An unparsable `R|` line within a shard is malformed. A valid-CRC row whose particle is absent from metadata is an unknown-particle row.

For each `(tick, particle)` key, retain only rows at the highest generation. Lower generations are superseded. If every highest-generation row has identical numeric coordinates, select the row from the lexicographically smallest shard ID and count the remaining equal rows as duplicates. If highest-generation coordinates disagree, the key conflicts and no row is selected. A timestep is complete only when every expected particle has one selected nonconflicting row. All selected rows, including rows from incomplete timesteps, belong in `recovered_records`; only complete timesteps enter trajectory reconstruction. Rejected timesteps are sorted by tick and use `conflicting-record` if any expected key conflicts, otherwise `missing-particle`.

## Canonical checkpoint and resume

The checkpoint is UTF-8 text with LF line endings and one final newline. It is canonical under shard-order and row-order changes. Within a checkpoint, shards are sorted by generation then shard ID, and each shard's trimmed `R|` lines are sorted lexicographically, including malformed, CRC-rejected, and unknown-particle lines.

The exact checkpoint lines are:

1. `schema|brownian-recovery-state/v2`
2. `meta|dt=<canonical>|box=<canonical>|particles=<metadata order>|fit=<start>:<end>`
3. For each shard: `shard|id=<ID>|generation=<generation>|records=<count>|sha256=<shard digest>`
4. Immediately after that shard header, one `record|<base64url>` line per sorted record. Base64url is UTF-8, URL-safe, and has no padding.
5. `sourceSha256|<source digest>`
6. `stateSha256|<state digest>`

Canonical decimal values use `BigDecimal.valueOf(value).stripTrailingZeros().toPlainString()`, with any zero represented as `0`. A shard digest is lowercase SHA-256 over each sorted raw `R|` line followed by `\n`. The source-digest preimage starts at the canonical `meta|` line and includes every canonical shard and record line, each with `\n`. The state-digest preimage is the schema line plus the complete source-digest preimage plus the `sourceSha256|...` line, each with `\n`. The `stateSha256` line is not part of its own preimage.

`analyze` creates this checkpoint from the definition. `resume` first verifies the existing checkpoint byte-for-byte, then canonicalizes the supplied definition. Metadata must be identical, and every shard ID already recorded in the checkpoint must still be present with the same generation, sorted record lines, and digest. New shard IDs may be added in any input order. Missing or changed prior shards exit 4 and preserve all artifacts. Repeating `resume` with no new shards is idempotent. The resumed checkpoint represents the complete supplied definition, and all scientific outputs are recomputed from that full checkpoint so a new higher-generation shard may repair or conflict with earlier observations.

`rebuild` verifies the checkpoint and derives the database and report from it without the original definition. For the same checkpoint, `resume` and `rebuild` reports must be byte-identical and their DuckDB user-table contents must be equivalent.

## Trajectory reconstruction and diffusion statistics

Sort complete ticks and split them into maximal consecutive-tick segments. At the first tick of each segment, corrected unwrapped coordinates `(ux,uy,uz)` and drift are zero for every particle. At each later tick and axis, calculate each particle's wrapped step `d=current-previous`; while `d > box/2`, subtract `box`, and while `d <= -box/2`, add `box`. Ensemble drift is the arithmetic mean wrapped step over all expected particles. Add `d-drift` to that particle's corrected unwrapped coordinate.

For lag `L`, use only pairs of ticks exactly `L` apart within the same segment. `pairs` counts particle-pairs. `msdX`, `msdY`, and `msdZ` are means of squared corrected displacement, and `msdTotal` is their sum. Emit every lag from 1 through `fit.end` with at least one pair.

Fit ordinary least squares with an intercept to `msdTotal` against physical time `lag*dt` for available lags in the inclusive fit range. At least three fitted points are required. Report slope, intercept, R², slope standard error `sqrt((SSE/(n-2))/Sxx)`, diffusion coefficient `slope/6`, and diffusion standard error `slopeStdErr/6`. Apply the same regression independently to each axis MSD and report axis diffusion as axis slope divided by 2. If `SST` is zero, R² is 1 when SSE is also zero and 0 otherwise.

## DuckDB contract

The database is created through JDBC and contains exactly these user tables and columns:

- `source_shards(shard_id VARCHAR, generation BIGINT, records BIGINT, shard_sha256 VARCHAR)` in checkpoint order.
- `recovered_records(tick BIGINT, particle_id VARCHAR, x DOUBLE, y DOUBLE, z DOUBLE, generation BIGINT, shard_id VARCHAR)` logically ordered by tick then particle ID.
- `trajectory_points(segment_id BIGINT, tick BIGINT, particle_id VARCHAR, x DOUBLE, y DOUBLE, z DOUBLE, ux DOUBLE, uy DOUBLE, uz DOUBLE, drift_x DOUBLE, drift_y DOUBLE, drift_z DOUBLE)` for complete timesteps only.
- `rejected_timesteps(tick BIGINT, reason VARCHAR)`.
- `msd_by_lag(lag BIGINT, time DOUBLE, pairs BIGINT, msd_x DOUBLE, msd_y DOUBLE, msd_z DOUBLE, msd_total DOUBLE)`.
- `analysis_manifest(schema VARCHAR, source_sha256 VARCHAR, state_sha256 VARCHAR, dataset_sha256 VARCHAR, complete_timesteps BIGINT, rejected_timesteps BIGINT)` with exactly one row.

## JSON report and digest coupling

The compact report has one trailing newline and exactly these top-level keys in order: `schema`, `simulation`, `recovery`, `sourceSha256`, `stateSha256`, `datasetSha256`, `msd`, `regression`. `schema` is `brownian-diffusion-report/v2`.

`simulation` keys are `dimensions`, `dt`, `boxLength`, `particles`, `fitLagStart`, `fitLagEnd`. `recovery` keys are `shardsSeen`, `recordsSeen`, `recordsValid`, `recordsRejectedMalformed`, `recordsRejectedCrc`, `recordsRejectedUnknownParticle`, `supersededDiscarded`, `duplicatesDiscarded`, `conflictingKeys`, `shardsApplied`, `completeTimesteps`, `rejectedTimesteps`. Each `shardsApplied` entry has `id`, `generation`, `records`, `sha256`. Each rejected entry has `tick`, `reason`.

`sourceSha256` and `stateSha256` exactly match the checkpoint lines and the single `analysis_manifest` row. `datasetSha256` is lowercase SHA-256 over selected rows from complete timesteps sorted by tick then particle ID. Each line is `tick|particle|x|y|z\n`, with coordinates rendered using the canonical decimal rule above. The manifest's `dataset_sha256` matches the report.

`msd` entries have `lag`, `time`, `pairs`, `msdX`, `msdY`, `msdZ`, `msdTotal`. `regression` has `lagsUsed`, `slope`, `intercept`, `rSquared`, `slopeStdErr`, `diffusionCoefficient`, `diffusionStdErr`, `axisDiffusion`; `axisDiffusion` has `x`, `y`, `z`.

All report floating-point numbers use exactly nine decimal places with half-up rounding, no scientific notation, and no negative zero. JSON key order, array order, integer versus floating type, null versus missing behavior, lowercase digest spelling, and the final newline are normative.

## Publication and path safety

For `analyze` and `resume`, checkpoint, database, and report paths must be pairwise distinct after absolute normalization. For `rebuild`, the input checkpoint and both output paths must be pairwise distinct. All new artifact bytes are prepared before existing targets are replaced. If publication of any requested artifact fails, the command exits 5 and restores all pre-existing requested artifacts without leaving partial temporary files beside them.
