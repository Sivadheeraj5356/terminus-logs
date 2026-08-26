Auroral lattice contract

The `fusion` binary reads calibration manifests, invokes the configured drift
probe to rank them, decodes every telemetry batch under the configured telemetry
directory, writes an event TSV, and writes an audit JSON document.

The command accepts these flags:

- `--telemetry-dir <absolute path>`
- `--calibration-dir <absolute path>`
- `--probe <absolute path>`
- `--probe-batch <absolute path>`
- `--out <absolute path>`
- `--audit-out <absolute path>`

The default paths are `/app/telemetry`, `/app/calibration`,
`/app/probe/driftprobe`, `/app/telemetry/public.cfr`,
`/app/output/events.tsv`, and `/app/output/audit.json`.

Calibration selection

Each calibration manifest is JSON. It contains labels, fixed-point scaling
arrays, zone and batch terms, per-class weights, quality terms, trend terms,
median terms, and pair interactions. The command must pass each manifest to the
configured probe as:

`<probe> --manifest <manifest-path> --batch <probe-batch-path>`

Probe output has this form:

`rank_score=<integer> drift=<integer> anchor=<8 lowercase or uppercase hex digits>`

Select the two compatible manifests with the lowest rank scores. Ties are
broken by calibration filename in ascending byte order. The selected manifests
receive ensemble weights `4` and `2`, in that order. If only one manifest is
available, use it with weight `4`. Selected manifests must have the same labels
and scale denominator.

Telemetry files

Process files under `--telemetry-dir` in filename order. Files may be single
batch `ALT1` containers or segmented `ALS2` containers. Each decoded row has a
frame id, zone, minute, feature values, quality mask, batch name, and batch mix.
Record checksums and container checksums must be validated. Any malformed input
must make the command exit non-zero without replacing either output file.

Packed feature lanes use these conventions:

- Zig-zag values use `(value << 1) ^ (value >> 31)` on encode and the inverse
  on decode.
- The width byte contains both bit-width and lane flags. For packed lanes, the
  bit width is `width & 0x0f` when either high packing/nibble flag `0xc0` is
  present; otherwise the bit width is `width & ~0x20`, so the quality-trailer
  flag `0x20` is not part of the packed bit width. When the zig-zag flag
  `0x80` is not set, unpacked fields are signed two's-complement values of that
  bit width.
- For route-ordered lanes, sensor positions start at `zone % dim` and step by
  `dim - 1`, modulo `dim`.
- Seeded XOR masks use
  `(mask ^ seed ^ ((frame_id >> 7) & 0xff) ^ ((zone & 7) * 29) ^ dim) & 0xff`.
- Residual lanes use predictor state when flag `0x02` is set. Initialize the
  predictor to `zone - 3` for each frame before reconstructing that frame's
  sensor values. First decode, de-mask, unpack, sparse-expand, rotate back, and
  scatter any route-ordered payload into a raw residual array indexed by decoded
  sensor position. Then apply the predictor over that output array in natural
  index order `0, 1, ..., dim-1`, not serialized route order. For each residual
  at index `i`, add it to the current predictor to get the absolute sensor value
  for `values[i]`, then set the predictor to that absolute value before moving
  to index `i + 1`.
- Segmented telemetry keeps one running minute-delta state for the whole ALS2
  container. Do not reset the previous minute when moving from one segment to
  the next; the first frame in segment `n + 1` is delta-decoded from the last
  absolute minute produced in segment `n`.
- Sparse lanes may use a bitmap or an explicit present-index list. Bitmap sparse
  lanes enumerate present indexes in route order when flag `0x10` is set and in
  natural index order otherwise. Explicit sparse lanes store the present count
  byte followed by the actual sensor indexes; use those listed indexes directly.
- Packed lanes may be rotated and may use nibble-swapped byte order. Undo XOR
  masking before reading sparse descriptors, then undo rotation and nibble swap
  on the payload before unpacking packed values.

Quality and feature centering

For manifest feature position `j`, compute
`source = (sensor_order[j] + zone_shift[zone]) % decoded_sensor_count`, where
`zone = frame_zone & 7`. Use that same `source` index both to read the decoded
sensor value from the frame and to test the frame quality mask bit. When
`quality & (1 << source)` is set, the feature's centered value is exactly `0`
before batch medians and scoring are computed. Otherwise, clip
`decoded_values[source]` to `clip_min[j]..clip_max[j]` and subtract `zero[j]`
to get the centered value for feature `j`.
The centered value is multiplied by `scale_num[j]` by the feature-weight and
median scoring terms. `scale_den` is used for fixed-point class terms and for
normalizing the final event margin.

Batch statistics

For each selected manifest and telemetry batch, compute the row count, batch mix,
zone counts, feature medians, minute min, minute max, and minute median used by
scoring. Feature medians are computed from the manifest-centered values after
quality masking. Medians use lower-median indexing: `(rows - 1) / 2` after
sorting. Audit `quality_counts` are batch-level raw sensor-bit counts, not
manifest-remapped feature counts.

Scoring

Score every decoded frame against every class in every selected manifest, then
combine class scores with the selected manifest weights. Scoring uses every
named calibration term:

- `bias_milli`
- `zone_bias_milli`
- `shard_bias_milli`
- `drift_bias_milli`
- `anchor_bias_milli`
- `mix_bias_milli`
- `load_bias_milli`
- `span_bias_milli`
- `time_bias_milli`
- `quality_bias_milli`
- `weights_milli`
- `quality_weights_milli`
- `median_milli`
- `pair_terms`

The trend contribution is
`trend_weights_milli[c][j] * centered_value[j] * minute_delta`, using the
clipped minute delta. Median terms use the frame's centered feature value minus
the batch feature median. Pair interactions use the product of the two centered
feature values multiplied by the pair coefficient.

Use these derived terms for class scoring:

- `zone = frame_zone & 7`
- `shard = ((frame_id >> 4) ^ zone ^ (anchor & 7)) & 7`
- `minute_delta = clamp(frame_minute - batch_minute_median, -64, 64)`
- `time_phase = (minute_delta + zone * 3 + (anchor & 15)) & 15`
- `span_bucket = (batch_minute_max - batch_minute_min) & 7`
- `qcount = number of manifest feature positions whose remapped quality bit is set`
- `anchor_term = ((anchor >> ((c * 7) % 17)) & 31) - 16`
- `mix_term = ((batch_mix >> ((zone + c) & 7)) & 15) - 8`
- `load_term = batch_zone_counts[zone] * 8 - batch_rows`

For class `c`, start with
`(bias_milli[c] + zone_bias_milli[zone][c] + shard_bias_milli[shard][c]) * scale_den`.
Also multiply `drift_bias_milli`, `anchor_bias_milli`, `mix_bias_milli`,
`load_bias_milli`, `span_bias_milli`, `time_bias_milli`, and
`quality_bias_milli` contributions by `scale_den`. For each feature `j`, add
`weights_milli[c][j] * centered_value[j] * scale_num[j]` and
`median_milli[c][j] * (centered_value[j] - batch_median[j]) * scale_num[j]`.
If the remapped quality bit for feature `j` is set, also add
`quality_weights_milli[c][j] * scale_den`; otherwise do not add that feature's
quality-weight term. Add the trend and pair contributions without an extra
`scale_den` factor. Each `pair_terms[c]` entry is `[left, right, weight]` and
contributes `weight * centered_value[left] * centered_value[right]`.

Class ordering

The winning class is the class with the highest combined score. The runner-up
is the next highest score. If class scores tie, keep the earlier label, meaning
the lower index in the manifest's `labels` array for both winner and runner-up.
The raw event margin is the winning combined score minus the runner-up combined
score. The emitted `margin_milli` is that raw margin divided by
`scale_den * total_selected_manifest_weight`, rounded to the nearest integer
with halves rounded away from zero. For positive raw margins, compute
`(raw + divisor / 2) / divisor` with integer division. For negative raw margins,
compute `-((-raw + divisor / 2) / divisor)`.

Event TSV

The event TSV is sorted by `frame_id` ascending. It has a header followed by one
row per decoded frame:

`frame_id	batch	minute	zone	event	margin_milli`

Frame ids are rendered as eight lowercase hexadecimal digits. Margins are
integers.

Audit JSON

The audit JSON contains:

- `manifests`: selected manifests in ensemble order, each with `name`,
  `rank_score`, `drift`, `anchor`, and `weight`
- `rows`: total decoded row count
- `batches`: one entry per batch name in ascending order, with `batch`, `rows`,
  `batch_mix`, `minute_min`, `minute_max`, `minute_median`, `zone_counts`, and
  `quality_counts`
- `events_sha256`: lowercase SHA-256 of the exact TSV bytes

`anchor` is an eight-character lowercase hexadecimal string. `zone_counts`
always has eight integers. `quality_counts` always has eight integers and counts
quality-marked raw decoded sensor bit positions 0 through 7 for each batch. This
audit field is intentionally raw-sensor based; feature centering still uses the
manifest remapping described above.

Output safety

Write outputs atomically. If decoding, probing, scoring, rendering, or writing
fails, the command must not replace existing `--out` or `--audit-out` files.
Write both output payloads to temporary sibling files first. Replace the final
event and audit paths only after both temporary writes have succeeded.
