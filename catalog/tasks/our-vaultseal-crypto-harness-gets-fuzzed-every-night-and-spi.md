# Our `vaultseal` crypto harness gets fuzzed every night and spits out a pile of g

Submission: `6b3ac7d8-fc5d-4da1-8785-f918ca4df0ad`  
Slug: `our-vaultseal-crypto-harness-gets-fuzzed-every-night-and-spi`  
Latest archive: `6b3ac7d8-fc5d-4da1-8785-f918ca4df0ad_submission_2026-07-05T23_35_39.212Z.zip`  
Revisions: 1

## Task summary

Our `vaultseal` crypto harness gets fuzzed every night and spits out a pile of gdb backtraces and valgrind memcheck logs, and a Terraform module in `/app/triage` turns that corpus into a single deterministic `triage_report.json` — classifying each crash, scrubbing key material, correlating the gdb and valgrind sides, clustering near-identical crashes, and failing `terraform apply` when anything trips the severity gate. It was passing its acceptance suite until yesterday's refactor. It still runs end to end and still writes a report, but the report is now wrong in several places: the refactor introduced regressions in the analysis logic, and they don't all show up on the small sample corpus, so a quick run can look fine while the module is still broken. You have a reference build of the engine — the way it behaved before the refactor — shipped as an opaque binary at `/app/oracle`. You can run it on any corpus you like:

Required artifacts include: `/app/triage`, `/app/oracle`, `/app/triage/scripts/analyze.py`, `/app/docs/TRIAGE_RUNBOOK.md`, `/app/corpus`, `/app/integration`.

Author anonymous tagged this **hard** security task (terraform, valgrind, gdb, cryptography, triage, clustering, reverse-engineering, differential-testing).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `6b3ac7d8-fc5d-4da1-8785-f918ca4df0ad_submission_2026-07-05T23_35_39.212Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
