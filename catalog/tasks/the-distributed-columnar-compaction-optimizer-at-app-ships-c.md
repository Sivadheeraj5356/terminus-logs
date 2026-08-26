# The distributed columnar compaction optimizer at /app ships columnarctl, a C++ C

Submission: `e699b548-c7ff-4c75-82b8-4e29abc52528`  
Slug: `the-distributed-columnar-compaction-optimizer-at-app-ships-c`  
Latest archive: `e699b548-c7ff-4c75-82b8-4e29abc52528_submission_2026-07-05T14_21_03.012Z.zip`  
Revisions in Dropbox: 1

## Task summary

The distributed columnar compaction optimizer at /app ships columnarctl, a C++ CLI that ingests CLFC binary fragment catalogs through a staging snapshot, exports merge plans across row-range overlaps, validates plans, and repairs broken orderings. The implementation does not match the published contracts. Behavioral rules, catalog layout, merge plan JSON, scan cost accounting, replica policy, and the ingest snapshot contract live under /app/docs/COMPACTION_CONTRACT.md and the other documents it references. Rebuild with make -C /app before testing. Invoking columnarctl with no arguments or with an unknown subcommand prints the single token USAGE on stderr and exits with status 2. All other failed subcommands print exactly one error token on stderr and a non-zero exit status as defined in /app/docs/COMPACTION_CONTRACT.md. Successful validate and repair emit one JSON object on stdout. Sample catalogs under /app/data/catalogs/ are for local experimentation; grading may use additional CLFC catalogs that are not shipped in the image but follow the same format.

Required artifacts include: `/app/docs/COMPACTION_CONTRACT.md`, `/app/data/catalogs/`.

Author anonymous tagged this **hard** data-processing task (columnar, compaction, replica, binary-catalog, multi-bug-repair).

Time estimates: expert ~200 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `e699b548-c7ff-4c75-82b8-4e29abc52528_submission_2026-07-05T14_21_03.012Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
