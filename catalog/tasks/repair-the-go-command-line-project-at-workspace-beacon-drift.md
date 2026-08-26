# Repair the Go command-line project at /workspace/beacon-drift-go-build-rescue so

Submission: `6eb2b426-ed78-4ec2-a060-4038a99d33ea`  
Slug: `repair-the-go-command-line-project-at-workspace-beacon-drift`  
Latest archive: `6eb2b426-ed78-4ec2-a060-4038a99d33ea_submission_2026-07-20T06_48_11.063Z.zip`  
Revisions in Dropbox: 2

## Task summary

Repair the Go command-line project at /workspace/beacon-drift-go-build-rescue so it behaves like a dependable offline release package for coastal operations staff. A fresh checkout must support the ordinary make workflow for cleaning, testing, building, and smoke verification without downloading anything, while keeping the module small and under its existing project identity. The test workflow should exercise the whole project, including internal packages, not only the command entry point. Operators build a command named beacon-drift, copy it to field laptops, and run it with a named operating profile, a packet file, and a report destination. The copied command must still understand the repository's policy data after it leaves the checkout. The canonical profile file belongs at /workspace/beacon-drift-go-build-rescue/config/beacon_profiles.json and must stay there. Any package-local copy used so Go can bundle that data is only temporary: internal/packets/config must not remain after clean, test, build, or smoke. Each make target should leave the checkout free of that staging directory and other supported build outputs unless the target's purpose is to create the release binary. Equivalent builds from equivalent checkouts should be reproducible, and generated binaries should not reveal the local checkout path.

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **hard** build-and-dependency-management task (go, make, go-modules, offline-build, reproducible-build, artifact-packaging).

Time estimates: expert ~60 min, junior ~120 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `6eb2b426-ed78-4ec2-a060-4038a99d33ea_submission_2026-07-20T06_48_11.063Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
