# The nightly clearing run on this host builds a postings tool entirely from vendo

Submission: `ef1c3782-c4d7-4b86-9f76-74ba4e1c57a0`  
Slug: `the-nightly-clearing-run-on-this-host-builds-a-postings-tool`  
Latest archive: `ef1c3782-c4d7-4b86-9f76-74ba4e1c57a0_submission_2026-07-20T13_02_07.631Z.zip`  
Revisions in Dropbox: 5

## Task summary

The nightly clearing run on this host builds a postings tool entirely from vendored sources and then uses it to turn a binary tape of settlement records into a postings report. Since a recent change to the tool the build still completes and the tool still runs, but downstream reconciliation keeps rejecting the report: the amounts come out right for the small shipped tape and wrong for larger ones. Everything the build needs is under /app/vendor and /app/build, and no network is available. The vendored kit at /app/vendor/reckit holds the record-format library recfmt.fs and the FORMAT descriptor, which together set out how one record frame is laid out and how each field is meant to be read from the tape. /app/build/assemble.sh places that library ahead of the unit /app/build/decode.fs and writes the assembled program to /app/build/tape.fs, and /app/build/run.sh performs that assembly and then runs the program. The assembled program takes two arguments, the path of an input tape and the path of the report to write; with no arguments it reads /app/data/records.bin and writes /app/data/report.txt.

Required artifacts include: `/app/vendor`, `/app/build`, `/app/vendor/reckit`, `/app/build/assemble.sh`, `/app/build/decode.fs`, `/app/build/tape.fs`, `/app/build/run.sh`, `/app/data/records.bin`.

Author anonymous tagged this **hard** build-and-dependency-management task (gforth, offline-build, vendored-sources, binary-records, byte-order).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `ef1c3782-c4d7-4b86-9f76-74ba4e1c57a0_submission_2026-07-20T13_02_07.631Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
