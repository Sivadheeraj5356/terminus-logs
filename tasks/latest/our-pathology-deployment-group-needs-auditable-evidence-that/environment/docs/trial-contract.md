This trial produces reproducible portability evidence from two immutable classifier exports. All paths, shapes, key orders, calculations, and failure behavior below are part of the interface.

## Invocation and trusted files

The evaluator accepts only `--manifest`, `--policy`, `--model-dir`, `--source`, and `--output`, each exactly once with an absolute normalized path. Success and failure both keep stdout empty. A failure returns nonzero, emits a concise stderr diagnostic, and never creates, truncates, or replaces the requested report.

The UTF-8 source-properties file and model directory must be regular non-symlinks. Properties have exactly these nonblank `key=value` lines in order: `repository`, `revision`, `mobilenet_v3_large.pt`, `mobilenet_v3_large.onnx`, `mobilenet_v3_large.onnx.data`, `config.json`. Revision is 40 lowercase hex characters and artifact values are 64 lowercase hex SHA-256 digests. Each named model file must be a regular non-symlink with that digest. `config.json.id2label` is a non-empty object whose keys, in order, are consecutive decimal indices from zero and whose values are unique, nonblank strings.

## Manifest, images, and policy

The non-symlink UTF-8 JSON Lines manifest is non-empty, has no BOM or blank lines, and rejects duplicate JSON keys. Every record has exactly `id`, `image`, `sha256`, `group` in that order, all nonblank strings; IDs are unique, `sha256` is 64 lowercase hex, and the bytes at `image` have that digest. Images are normalized relative paths beneath the manifest directory. Absolute paths, `.`, `..`, backslashes, symlink components, escapes, and non-regular targets are invalid.

Images are ASCII P3 PPM. ASCII whitespace and `#` comments separate tokens. Width and height are integers in `[1,4096]`, max value is in `[1,65535]`, and exactly `width * height * 3` integer samples in `[0,max]` follow. Reject non-ASCII bytes, malformed integers, extra/missing samples, and decoded rasters above 50,000,000 samples.

Policy keys are exactly `top_k`, `max_probability_drift`, `max_batch_drift`, `max_js_divergence`, `batch_sizes`, `required_groups`, in order. `top_k` is an integer in `[1,label_count]`; all three limits are finite JSON numbers in `[0,1]`. Batch sizes are unique positive integers, strictly increasing from 1, and at most the sample count. Required groups are nonblank unique strings in strictly increasing Unicode code-point order and equal the set of manifest groups.

## Tensor and engine calculations

Decode RGB as `sample/max`. Bilinearly resize the shorter edge to 256. The other dimension is the nearest integer to `original*256/shorter`, choosing the lower integer at an exact half; equivalently for these positive dimensions, `ceil(original*256/shorter - 0.5)`. Thus an original `513 x 512` image resizes to `256 x 256`, not `257 x 256`. Map pixel centers by `(destination+0.5)*source/destination-0.5`, clamping source coordinates to the edge. Center-crop 224 using integer offsets `(dimension-224)/2`. Normalize channels using means `[0.485,0.456,0.406]` and standard deviations `[0.229,0.224,0.225]`, then cast each value to float32 and lay out one shared NCHW tensor. Its fingerprint is lowercase SHA-256 over the NCHW float32 values encoded consecutively as IEEE-754 little-endian bytes.

Run the shared tensor through DJL engine `PyTorch` with `mobilenet_v3_large.pt` and `OnnxRuntime` with `mobilenet_v3_large.onnx`. Output must be one finite `[batch,label_count]` logits tensor. Apply stable softmax per row. Rank descending probability, breaking exact ties by lower label index.

For each batch size, partition manifest order into consecutive chunks no larger than that size. A profile is supported only when every invocation accepts the tensor and returns one row per input and one column per label. Native rejection or a wrong batch dimension makes a size above one unsupported instead of aborting. Batch one must be supported by both engines.

Maximum drift is the largest absolute component difference. Jensen–Shannon divergence uses base-2 logarithms and midpoint `(p+q)/2`, so it lies in `[0,1]`; zero-probability terms contribute zero. Engine batch drift compares a profile with its engine's batch-one vector. Cross-engine metrics compare engines at the same profile. Exact top-k index lists must match. Gate comparisons use unrounded values and equality passes. A sample passes only if every profile is supported by both engines, both cross-engine metrics meet their limits, both batch drifts meet the batch limit, and rankings match. A group gate is the conjunction of its manifest members, and the portability gate is the conjunction of all sample and required-group gates.

## Report and durable publication

Write compact UTF-8 JSON plus one newline. Keys and arrays retain the orders below. Every probability and metric is decimal half-up rounded to eight places with negative zero rendered as zero. To keep the evidence self-consistent, displayed drift and Jensen–Shannon values are calculated from the already rounded profile probability values stored in the report; gate decisions still use raw values.

Top-level keys: `schema_version`, `model`, `preprocessing`, `policy`, `samples`, `summary`; schema version is `2`. Model keys are `repository`, `revision`, `artifacts`; artifacts follow source order with `file`, `sha256`. Preprocessing keys are `resize_shorter`, `crop_size`, `layout`, `channel_order`, `scale`, `mean`, `std`, `tensor_fingerprint`, with values `256`, `224`, `NCHW`, `RGB`, `1/max_value`, the vectors above, and `sha256-f32le-nchw`. Policy reproduces its six input keys and values.

Sample keys are `id`, `image`, `sha256`, `group`, `tensor_sha256`, `engines`, `profiles`, `gate_pass`. Engines are `pytorch`, `onnxruntime`; each contains `probabilities`, `top_k` from batch one. An engine-level top-k item is an object containing `index`, `label`, `probability`. Profiles follow policy order and contain `batch_size`, `pytorch_batch_supported`, `onnxruntime_batch_supported`, `pytorch_probabilities`, `onnxruntime_probabilities`, `cross_engine_max_drift`, `cross_engine_js_divergence`, `pytorch_batch_max_drift`, `onnxruntime_batch_max_drift`, `pytorch_top_k`, `onnxruntime_top_k`, `top_k_match`. Unlike the engine-level object arrays, each supported profile-level `pytorch_top_k` and `onnxruntime_top_k` value is a plain JSON array of integer class indices. Unsupported probability vectors, metrics, and rankings are null and match is false.

Summary keys are `sample_count`, `group_results`, `all_batch_sizes_supported`, `all_top_k_match`, `max_probability_drift`, `max_js_divergence`, `max_batch_drift`, `portability_gate`. Group results follow `required_groups` and contain `group`, `sample_count`, `gate_pass`, `max_probability_drift`, `max_js_divergence`, `max_batch_drift`. Maxima cover supported displayed comparisons.

The output and every existing path component must not be symlinks. Create missing parent directories, write through a uniquely named sibling temporary file, fsync its completed content, atomically replace the output, then fsync the parent directory. Always remove the unique temporary after a failed publication. Never touch an unrelated sibling named `<output>.tmp`.
