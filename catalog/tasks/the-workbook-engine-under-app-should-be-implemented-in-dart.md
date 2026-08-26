# The workbook engine under /app should be implemented in Dart only. Put the sourc

Submission: `257d3792-585b-4de0-bb6d-957ba12ad7d0`  
Slug: `the-workbook-engine-under-app-should-be-implemented-in-dart`  
Latest archive: `257d3792-585b-4de0-bb6d-957ba12ad7d0_submission_2026-07-04T03_42_15.182Z.zip`  
Revisions: 1

## Task summary

The workbook engine under /app should be implemented in Dart only. Put the source under /app/src and make /app/src/main.dart the runnable entrypoint. The verifier runs it directly as `dart /app/src/main.dart <input-json> <output-dir>`, not through `dart run`. It must work with arbitrary input and output paths, fail nonzero for a missing input file, overwrite stale output files, and write deterministic JSON stage files into the requested output directory. The full spreadsheet contract is in /app/docs/SPEC.md. Follow that document for formula discovery, dependency extraction, edit timing, recalculation, cycle/error handling, named ranges, output schemas, sorting, and checksums. In particular, the audit stages use the final post-edit formula registry, while the dependency graph is the graph discovered before edits are applied; formulas introduced by edits still appear in final formula/audit/metric counts, but have no pre-edit dependency row expansion beyond the empty default described in the spec. Do not use Python or another helper interpreter from the Dart solution.

Required artifacts include: `/app/src`, `/app/src/main.dart`, `/app/docs/SPEC.md`.

Author Anonymous tagged this **hard** data-processing task (dart, spreadsheet, formula-engine, recalculation, cycles).

Time estimates: expert ~240.0 min, junior ~1800.0 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `257d3792-585b-4de0-bb6d-957ba12ad7d0_submission_2026-07-04T03_42_15.182Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
