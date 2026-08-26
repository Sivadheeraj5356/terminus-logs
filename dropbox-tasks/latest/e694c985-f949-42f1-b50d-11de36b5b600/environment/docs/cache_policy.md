# FlowerVision cache policy (v2)

## Namespaced Redis keys

Inference cache entries use:

`ml:v2:model:<model>:user:<user_id>:image:<image_id>`

Example: `ml:v2:model:flower:user:alice:image:rose001`

Legacy keys (pre-migration):

- `flower_prediction:<image_id>` → user `default`
- `flower_prediction:<user_id>:<image_id>` → explicit user scope

## Feature checksum

After resizing to 224×224 RGB pixels, the checksum is SHA256 of the ASCII prefix
`<source_width>x<source_height>:` concatenated with the raw RGB byte buffer.
Source dimensions come from the original file via ImageMagick `identify`.

## Stale entry removal

Drop migrated entries when any of the following hold:

- JSON parse failure
- missing `checksum` or `prediction`
- `feature_version` != `v2`
- `expires_at` in the past
- `checksum` mismatch vs a fresh extractor run for the image id
- `mean_rgb` mismatch vs a fresh extractor run for the image id

## Migration manifest

`/tmp/redis_migration_manifest.json`:

```json
{
  "schema_version": "1",
  "migrated": 0,
  "removed": 0,
  "failed": 0
}
```

## InferenceService.predict

`InferenceService.predict(image_id:, user_id: "default")` returns a Ruby hash with:

- `class` — string flower label
- `confidence` — numeric score
- `feature_version` — always `"v2"`
- `cache` — `"hit"` or `"miss"`

On a cache hit, validate the stored entry against a fresh extractor run for that
image. If `checksum` or `mean_rgb` does not match (or the entry fails
`CacheValidator`), delete the key, bump the invalid-removal counter, regenerate
features, and return `cache: "miss"`.

## Inference API

`POST /api/v1/predict`

Request JSON:

```json
{ "image_id": "flower001", "user_id": "alice" }
```

`user_id` defaults to `default` when omitted.

Response JSON (maps from the service hash above):

```json
{
  "prediction": "rose",
  "confidence": 0.93,
  "cache_status": "hit"
}
```

`prediction` ← `class`, `cache_status` ← `cache`. `confidence` is rounded to two
decimal places in the HTTP response.

## Audit report

`/app/output/inference_audit.json` includes:

`total_predictions`, `cache_hits`, `cache_misses`, `invalid_entries_removed`,
`feature_version` (`v2`), and `users_seen` (sorted unique user ids from counters).
