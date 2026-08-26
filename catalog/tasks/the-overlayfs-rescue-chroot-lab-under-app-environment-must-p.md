# The overlayfs rescue chroot lab under `/app/environment` must produce a consiste

Submission: `5d8a0bc1-9647-4168-8e6f-b1129c056ca8`  
Slug: `the-overlayfs-rescue-chroot-lab-under-app-environment-must-p`  
Latest archive: `5d8a0bc1-9647-4168-8e6f-b1129c056ca8_submission_2026-07-20T07_02_53.885Z.zip`  
Revisions in Dropbox: 1

## Task summary

The overlayfs rescue chroot lab under `/app/environment` must produce a consistent guard intersection across the public matrix. Training layouts (`train_a`, `train_b`) already look fine in smoke and in `/app/environment/kit/q9/q9_probe.json`, but held-out arms (`adv_c`, `adv_d`) still disagree on digests between the uninterrupted path and the recovered path, especially under whiteout or opaque merges, nested bind under chroot, and workdir/upperdir sibling checks. Text tails under `/app/environment/kit/logs/` are incomplete; authoritative mount bytes live in `/app/environment/kit/blk/*.mnt`. Build with `bash /app/environment/scripts/build_all.sh`, then run `/app/environment/bin/og_check --full-matrix --out /app/output/invariant_proof_log.json`. The checker must exit 0 for every arm. Proof-log schema, digest computation, band conditions, and the idempotent recovery command live in `/app/environment/docs/pact_ov7.md` (slice layout in `/app/environment/docs/slice_layout.md`). For each arm, uninterrupted and recovered `guard_trace` values must match, and a second recovery cycle must keep digests stable. Repeat recovery only via `bash /app/environment/migrations/mig_ov.sh --restore-anchors`.

Required artifacts include: `/app/environment`, `/app/environment/kit/q9/q9_probe.json`, `/app/environment/kit/logs/`, `/app/environment/kit/blk/*.mnt`, `/app/environment/scripts/build_all.sh`, `/app/environment/bin/og_check`, `/app/output/invariant_proof_log.json`, `/app/environment/docs/pact_ov7.md`.

Author anonymous tagged this **hard** system-administration task (java, overlayfs, chroot, rescue, mounts, whiteout).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `5d8a0bc1-9647-4168-8e6f-b1129c056ca8_submission_2026-07-20T07_02_53.885Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
