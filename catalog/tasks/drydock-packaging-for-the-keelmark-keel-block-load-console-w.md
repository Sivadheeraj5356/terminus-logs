# Drydock packaging for the Keelmark keel-block load console will not build. The c

Submission: `c6ccb710-577e-4680-8bd5-bd8a7f589007`  
Slug: `drydock-packaging-for-the-keelmark-keel-block-load-console-w`  
Latest archive: `c6ccb710-577e-4680-8bd5-bd8a7f589007_submission_2026-07-19T17_59_28.560Z.zip`  
Revisions: 2

## Task summary

Drydock packaging for the Keelmark keel-block load console will not build. The console is a multi-package Cabal workspace under /app, and during a rushed toolchain migration its packaging metadata drifted and three maintained modules never landed under the shipped source trees: Keelmark.Scan, Keelmark.Classify, and Keelmark.Emit exist only as retired 8.10-era copies under each package's compat tree. Types and Main under src/app are intact; Scan, Classify, and Emit must be restored under the maintained src trees so they match the normative ledger, not the tide sheet. Harbor ops needs the packaging restored and those modules reconstituted so the console builds offline and the packaging gate runs before the next flood-tide window. The workspace spans an internal core library, a report library, and an executable package, joined by the workspace project file. Everything must build with no network access and no Hackage fetches, resolving only against the toolchain's preinstalled package database — so any dependency bound, constraint, or version pin that reaches for something the offline database does not carry has to be brought back in line with what is actually installed rather than upgraded toward a newer release. The project must expose a Cabal package named keelmark whose version equals the edition policy's package_version and that builds an executable named keelmark, keeping aeson among the build dependencies for JSON handling. The internal libraries must expose the modules their dependents import, depend on one another in the correct direction without forming a build...

Required artifacts include: `/app/docs`, `/app/keelmark.sh`, `/app/bin/keelmark`, `/app/keelmark-policy`, `/app/keelmark-shards`, `/app/keelmark-ledger`, `/app/output/pack_inventory.json`, `/app/output/tension_alerts.json`.

Author anonymous tagged this **hard** build-and-dependency-management task (haskell, cabal, ghc, console-utility, packaging, offline-build).

Time estimates: expert ~150 min, junior ~280 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `c6ccb710-577e-4680-8bd5-bd8a7f589007_submission_2026-07-19T17_59_28.560Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
