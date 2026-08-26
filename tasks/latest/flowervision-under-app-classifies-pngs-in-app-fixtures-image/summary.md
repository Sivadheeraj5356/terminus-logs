# FlowerVision under `/app` classifies PNGs in `/app/fixtures/images`, but feature

- **UUID:** `e694c985-f949-42f1-b50d-11de36b5b600`
- **Slug:** `flowervision-under-app-classifies-pngs-in-app-fixtures-image`
- **Category:** machine-learning
- **Difficulty:** medium

## Summary

FlowerVision under `/app` classifies PNGs in `/app/fixtures/images`, but feature extraction is broken — `bundle exec ruby /app/scripts/test_features.rb` fails on the stub in `/app/lib/image_feature_extractor.rb`. Implement `ImageFeatureExtractor.extract(image_path)` and `FeatureSerializer.serialize(features)` per `/app/docs/cache_policy.md`.

ALL rules in that policy are mandatory and tested: 224×224 canvas, integer `mean_rgb`, checksum with the `<source_width>x<source_height>:` prefix over resized RGB bytes, serializer field order `width`, `height`, `mean_rgb`, `checksum` (no timestamps or random ids). Same image path twice must yield identical features.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
