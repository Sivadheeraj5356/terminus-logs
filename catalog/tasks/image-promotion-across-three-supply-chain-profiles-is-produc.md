# Image promotion across three supply-chain profiles is producing inconsistent

Submission: `40448e90-7afe-4bf0-bbb7-b1a41e00885c`  
Slug: `image-promotion-across-three-supply-chain-profiles-is-produc`  
Latest archive: `40448e90-7afe-4bf0-bbb7-b1a41e00885c_submission_2026-07-11T12_33_27.589Z.zip`  
Revisions in Dropbox: 1

## Task summary

Image promotion across three supply-chain profiles is producing inconsistent `/app/output/kv_export.json` reports. Content fingerprints disagree with the trust authority, stage transcripts fail replay checks, some runs disappear from the session export, and a mid-session loss of `/app/state/mirror_view.json` no longer yields the same export as an uninterrupted run—especially while a replica lag profile is still catching up. The pipeline lives under `/app/environment`. Stage binaries, rebuild, and run order are in `/app/environment/docs/matrix_cmds.md`. Hand-written JSON is insufficient; the verifier clears outputs and regenerates them through the normal pipeline.

Required artifacts include: `/app/output/kv_export.json`, `/app/state/mirror_view.json`, `/app/environment`, `/app/environment/docs/matrix_cmds.md`, `/app/environment/docs/stage_contract.md`, `/app/environment/docs/row_export.md`, `/app/environment/docs/seed_timelines.md`.

Author anonymous tagged this **hard** security task (supply-chain, content-trust, delegation, mirror-lag, go).

Time estimates: expert ~60 min, junior ~180 min.

Harbor timeouts: agent 1200s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `40448e90-7afe-4bf0-bbb7-b1a41e00885c_submission_2026-07-11T12_33_27.589Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
