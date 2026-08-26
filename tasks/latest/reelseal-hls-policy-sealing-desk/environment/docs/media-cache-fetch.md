# Media-cache fetch contract

Source object path: /app/fixtures/media-cache/bbb-sample.mp4
Fetch receipt path: /app/state/media-fetch.json

| Field | Type | Rule |
|-------|------|------|
| schema | string | reelseal.fetch/v1 |
| engine | string | reelseal-runtime/v1 |
| source_path | string | absolute path used |
| media_digest | string | sha256 hex of raw bytes |
| bytes | int | file size |

Fetch must refuse paths under /app/legacy. Digests use lowercase hex without a sha256: prefix.
