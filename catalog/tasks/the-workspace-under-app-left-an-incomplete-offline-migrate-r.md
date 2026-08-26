# The workspace under `/app` left an incomplete offline migrate: release-train sel

Submission: `75810cea-7647-47ec-ba76-2ecdd18bac3f`  
Slug: `the-workspace-under-app-left-an-incomplete-offline-migrate-r`  
Latest archive: `75810cea-7647-47ec-ba76-2ecdd18bac3f_submission_2026-07-18T08_41_27.158Z.zip`  
Revisions: 1

## Task summary

The workspace under `/app` left an incomplete offline migrate: release-train selection, channel windows, extension peer closure, content-addressed store packing, and the migrate journal no longer converge. Frozen installs and seal audits fail after the interrupted cycle in this pnpm monorepo lab. Correct the migrate pipeline sources under `/app` so `/app/tools/pnpm run verify:all` succeeds (resume, seal, offline frozen install, build, and `/app/tools/pnpm run audit:seal`). Follow `/app/docs/offline-workflow.md`, `/app/docs/train-contract.md`, `/app/docs/channel-contract.md`, `/app/docs/extension-contract.md`, `/app/docs/pack-contract.md`, and `/app/docs/journal-contract.md`.

Required artifacts include: `/app/tools/pnpm`, `/app/docs/offline-workflow.md`, `/app/docs/train-contract.md`, `/app/docs/channel-contract.md`, `/app/docs/extension-contract.md`, `/app/docs/pack-contract.md`, `/app/docs/journal-contract.md`, `/app/generated/plan-graph.json`.

Author anonymous tagged this **hard** build-and-dependency-management task (pnpm, monorepo, release-train, offline-store, migrate-journal).

Time estimates: expert ~180 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `75810cea-7647-47ec-ba76-2ecdd18bac3f_submission_2026-07-18T08_41_27.158Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
