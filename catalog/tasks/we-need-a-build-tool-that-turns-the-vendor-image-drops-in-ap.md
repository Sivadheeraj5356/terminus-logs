# We need a build tool that turns the vendor image drops in /app/assets/src into t

Submission: `d66c4a28-bb7a-4bf0-a67f-3786324495f2`  
Slug: `we-need-a-build-tool-that-turns-the-vendor-image-drops-in-ap`  
Latest archive: `d66c4a28-bb7a-4bf0-a67f-3786324495f2_submission_2026-07-06T00_05_37.784Z.zip`  
Revisions in Dropbox: 3

## Task summary

We need a build tool that turns the vendor image drops in /app/assets/src into the exact derivatives our CDN expects. Every rule for this — target sizes per asset class, when to crop versus fit, how to normalize camera orientation, the color profile policy, the output naming, and the manifest layout — is written up in /app/spec/asset_processing_spec.md. Please read the whole thing; the rules differ by asset class and some only appear once, in prose rather than a table. Each source file's asset class comes from /app/assets/src/manifest_inputs.csv. Build a C++ tool using the CMake setup already in /app so that /app/build/derive, given the sources directory, the CSV, and the spec path, produces every required derivative under /app/out/derivatives and writes /app/out/manifest.json describing what it produced, in the order the spec requires, with a content hash per output. Use ImageMagick for the actual image work.

Required artifacts include: `/app/assets/src`, `/app/spec/asset_processing_spec.md`, `/app/assets/src/manifest_inputs.csv`, `/app/build/derive`, `/app/out/derivatives`, `/app/out/manifest.json`, `/app/assets`.

Author anonymous tagged this **hard** data-processing task (imagemagick, exif-orientation, icc-color-profile, content-hash-manifest, deterministic-build).

Time estimates: expert ~90 min, junior ~300 min.

Harbor timeouts: agent 1200.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `d66c4a28-bb7a-4bf0-a67f-3786324495f2_submission_2026-07-06T00_05_37.784Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
