# Subvolume parity tooling under `/app` drifts after operator interruption, retry,

Submission: `7b41e0fc-40f3-440f-b620-d4eabca0cbaa`  
Slug: `subvolume-parity-tooling-under-app-drifts-after-operator-int`  
Latest archive: `7b41e0fc-40f3-440f-b620-d4eabca0cbaa_submission_2026-07-07T13_54_33.791Z.zip`  
Revisions in Dropbox: 1

## Task summary

Subvolume parity tooling under `/app` drifts after operator interruption, retry, warm memo reuse, or reload overlays: row stamps, summary folds, and the stream sidecar disagree even when bundled lane fixtures remain valid, and warm memo entries can leave row stamps looking locally coherent while summary folds and stream sidecars still disagree after matrix-all completes. Correct the m6_ctl crate sources under `/app/environment` so the matrix runner regenerates `/app/output/bw_emit.json` and `/app/output/stream_sidecar.bin` through matrix-all; hand-written JSON, cache deletion alone, static output writes, and test edits are insufficient because the verifier rebuilds with `cargo build --release --locked` and reruns matrix-all. Install the rebuilt CLI at `/app/bin/m6_ctl`, run `m6_ctl matrix-all`, and emit JSON following the bw_emit_v1 layout in `/app/environment/schemas/report_fields.toml` with top-level `rows` and `summary`; the summary `lineage_digest` must agree with the regenerated stream sidecar. Derivations, pass ordering, digest fold ordering, memo semantics, sidecar encoding, and remaining summary fields are in `/app/environment/docs/fc0_contract.md`. Bundled fixture ids are in `/app/environment/docs/lane_ids.txt` where `lane_alpha` is defined as the bundled alpha lane whose reload overlays must replace its base row at a higher wrap_epoch; operator argv patterns are in `/app/environment/docs/operator_cmds.txt`; runtime state lives under `/app/var/`. If a prior matrix pass left memo entries on disk, follow the idempotent recovery step in `fc0_contract.md` before...

Required artifacts include: `/app/environment`, `/app/output/bw_emit.json`, `/app/output/stream_sidecar.bin`, `/app/bin/m6_ctl`, `/app/environment/schemas/report_fields.toml`, `/app/environment/docs/fc0_contract.md`, `/app/environment/docs/lane_ids.txt`, `/app/environment/docs/operator_cmds.txt`.

Author anonymous tagged this **hard** system-administration task (btrfs, incremental-send, lineage, recovery, cache).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 650s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `7b41e0fc-40f3-440f-b620-d4eabca0cbaa_submission_2026-07-07T13_54_33.791Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
