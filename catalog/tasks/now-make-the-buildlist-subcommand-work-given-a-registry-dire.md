# Now make the buildlist subcommand work. Given a registry directory and a main

Submission: `f1c70a05-4e2d-4085-91c9-6c9bed3cee27`  
Slug: `now-make-the-buildlist-subcommand-work-given-a-registry-dire`  
Latest archive: `f1c70a05-4e2d-4085-91c9-6c9bed3cee27_submission_2026-07-11T05_51_33.677Z.zip`  
Revisions: 1

## Task summary

Now make the buildlist subcommand work. Given a registry directory and a main module manifest, it computes the build list, the map from each module reached in the transitive graph to its selected version, and writes it as the JSON in /app/app/docs/CLI.md. The walk starts from the main module and reads a module version's manifest only at the moment it first needs it, following require directives outward until no new module version is reached. Manifests the walk never reaches are never read. For each distinct module in the graph the selected version is the highest version that anything in the graph requires of it. A require names a minimum, so the selection is the maximum over every minimum requested anywhere, and there is no search and no revising of a choice once it is made. A version that merely exists in the registry but that nobody requires is never selected, and a later higher requirement for a module pulls in that higher manifest too and contributes whatever it requires. The main module itself is never a key in the build list, and the build list is empty when the main module requires nothing.

Required artifacts include: `/app/app/docs/CLI.md`.

Author anonymous tagged this **hard** build-and-dependency-management task (scala, dependency-resolution, version-selection, module-graph, pruning).

Time estimates: expert ~210 min, junior ~540 min.

Harbor timeouts: agent 1200.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `f1c70a05-4e2d-4085-91c9-6c9bed3cee27_submission_2026-07-11T05_51_33.677Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
