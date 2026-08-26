# # ReelSeal HLS policy sealing desk

Submission: `10de653f-0913-4752-8067-d381a772d1ef`  
Slug: `reelseal-hls-policy-sealing-desk`  
Latest archive: `10de653f-0913-4752-8067-d381a772d1ef_submission_2026-07-17T17_18_26.170Z.zip`  
Revisions: 2

## Task summary

This operational workflow on the ReelSeal facility desk under /app must deliver schema-valid encryption-manifest artifacts for AES-128 HLS sealing. Media release operators migrate sealing away from the legacy YAML and TOML configs under /app/legacy. Those configs describe HLS outputs but leak key URIs and omit release provenance. Security reviewers require a packaged release that satisfies the cited contracts. The image already ships a partially implemented Gin policy API, a Go command pipeline, FFmpeg tooling, an offline Big Buck Bunny media-cache object that stands in for the historical GCS sample, git hook stubs, and GPG release material. Network access is disabled; media must be taken from the local media-cache mirror. Archival helpers under /app/decoy are outside the sealing path.

Required artifacts include: `/app/legacy`, `/app/decoy`, `/app/state/media-fetch.json`, `/app/state/hls/`, `/app/state/hls/index.m3u8`, `/app/state/policy-bind.json`, `/app/output/encryption-manifest.json`, `/app/state/validation-stamp.json`.

Author anonymous tagged this **hard** security task (hls-aes128-sealing, gin-policy-api, release-provenance, gpg-tag-gate, git-hook-validation, key-uri-containment).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `10de653f-0913-4752-8067-d381a772d1ef_submission_2026-07-17T17_18_26.170Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through. Git history or refs are only partially repaired.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
