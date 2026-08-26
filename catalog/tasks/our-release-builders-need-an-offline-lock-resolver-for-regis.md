# Our release builders need an offline lock resolver for registries whose releases

Submission: `f19973d2-4637-4d9c-a00b-9dc5b09d59da`  
Slug: `our-release-builders-need-an-offline-lock-resolver-for-regis`  
Latest archive: `f19973d2-4637-4d9c-a00b-9dc5b09d59da_submission_2026-07-19T15_44_35.195Z.zip`  
Revisions: 3

## Task summary

Our release builders need an offline lock resolver for registries whose releases can expose several ABI-tagged capabilities. Build it as a Rust native executable so the same resolver can be rerun for different targets and policy profiles. Create /opt/linkseal/src/main.rs and compile /opt/linkseal/bin/linkseal as an ELF binary. The command is:

Required artifacts include: not named as `/app` paths.

Author Anonymous tagged this **hard** build-and-dependency-management task (rust, offline-lockfile, dependency-resolution, abi-compatibility, toolchain-policy, reproducible-builds).

Time estimates: expert ~420.0 min, junior ~1800.0 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `f19973d2-4637-4d9c-a00b-9dc5b09d59da_submission_2026-07-19T15_44_35.195Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
