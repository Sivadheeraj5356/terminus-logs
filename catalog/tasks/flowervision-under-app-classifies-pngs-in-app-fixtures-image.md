# FlowerVision under `/app` classifies PNGs in `/app/fixtures/images`, but feature

Submission: `e694c985-f949-42f1-b50d-11de36b5b600`  
Slug: `flowervision-under-app-classifies-pngs-in-app-fixtures-image`  
Latest archive: `e694c985-f949-42f1-b50d-11de36b5b600_submission_2026-07-12T21_11_14.270Z.zip`  
Revisions: 4

## Task summary

FlowerVision under `/app` classifies PNGs in `/app/fixtures/images`, but feature extraction is broken — `bundle exec ruby /app/scripts/test_features.rb` fails on the stub in `/app/lib/image_feature_extractor.rb`. Implement `ImageFeatureExtractor.extract(image_path)` and `FeatureSerializer.serialize(features)` per `/app/docs/cache_policy.md`. ALL rules in that policy are mandatory and tested: 224×224 canvas, integer `mean_rgb`, checksum with the `<source_width>x<source_height>:` prefix over resized RGB bytes, serializer field order `width`, `height`, `mean_rgb`, `checksum` (no timestamps or random ids). Same image path twice must yield identical features.

Required artifacts include: `/app/fixtures/images`, `/app/scripts/test_features.rb`, `/app/lib/image_feature_extractor.rb`, `/app/docs/cache_policy.md`.

Author anonymous tagged this **medium** machine-learning task (redis, imagemagick, caching, rails, inference).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1200.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `e694c985-f949-42f1-b50d-11de36b5b600_submission_2026-07-12T21_11_14.270Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
