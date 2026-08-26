# Finish the unfinished pnpm workspace cutover and Rust auditor under /app. Overri

Submission: `ecf8e7f3-557e-4c68-be27-a2d8011d80e9`  
Slug: `finish-the-unfinished-pnpm-workspace-cutover-and-rust-audito`  
Latest archive: `ecf8e7f3-557e-4c68-be27-a2d8011d80e9_submission_2026-07-15T17_53_43.041Z.zip`  
Revisions in Dropbox: 1

## Task summary

Finish the unfinished pnpm workspace cutover and Rust auditor under /app. Overrides still hit public registry, store may be stubbed, lockfile digests drift, provides collide, and packaging is unfinished. Deliverables: repair overrides/deps.csv; implement `pnpmfix inspect`; finish fail-closed release.sh.

Required artifacts include: `/app/pnpm-store/…tgz`, `/app/pnpm-store`, `/app/config/deps.csv`, `/app/config/pins.csv`, `/app/dist/pnpm-report.json`, `/app/dist/release-manifest.json`, `/app/dist/checksums.sha256`.

Author anonymous tagged this **medium** build-and-dependency-management task (pnpm, workspace-overrides, offline-build, cargo-workspace, release-packaging).

Time estimates: expert ~200 min, junior ~400 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `ecf8e7f3-557e-4c68-be27-a2d8011d80e9_submission_2026-07-15T17_53_43.041Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
