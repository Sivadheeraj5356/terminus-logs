# Scientific-computing undersea WDM optical-channel and Raman-pump caselab under `

Submission: `b019bbdc-3fdc-4a95-a630-057457614080`  
Slug: `scientific-computing-undersea-wdm-optical-channel-and-raman-`  
Latest archive: `b019bbdc-3fdc-4a95-a630-057457614080_submission_2026-07-19T04_19_15.639Z.zip`  
Revisions in Dropbox: 2

## Task summary

Scientific-computing undersea WDM optical-channel and Raman-pump caselab under `/app/environment`. On the chains in `/app/environment/docs/runbook.md`, `/app/output/replan_report.json`, `/app/output/lambda_trace.csv`, `/app/output/settle_score.tsv`, `/app/var/splicekit/pump_ledger.json`, `/app/var/splicekit/journal.jsonl`, and `splicectl status` disagree with each other and with independent replay of the fixtures under `/app/data/scenarios`. Wavelength continuity, regenerator remux, Raman cool-residual carry across commits and idle spans, demand admission ordering, per-span capacity on every routed hop with gbps accumulated from earlier admissions in the same run, shortest-path tie-breaks, settlement shares, digest packing, journal generation with prior digest linkage, and cross-artifact agreement misfire across runs. Subsystem numeric policy is defined in `/app/environment/docs/contract.md`. Unknown and empty-demand scenario ids exit non-zero with no `/app/output/` artifacts; publish without a completed run exits non-zero under the same rule. Digests are lowercase hex; external checks use `sha256sum`. The first post-reset commit exposes an empty prior digest field on report and status JSON; each later commit in the same session must echo the preceding successful digest on those surfaces per `/app/environment/docs/contract.md`.

Required artifacts include: `/app/environment`, `/app/environment/docs/runbook.md`, `/app/output/replan_report.json`, `/app/output/lambda_trace.csv`, `/app/output/settle_score.tsv`, `/app/var/splicekit/pump_ledger.json`, `/app/var/splicekit/journal.jsonl`, `/app/data/scenarios`.

Author anonymous tagged this **hard** scientific-computing task (scientific-computing, optical, wdm, raman, photonics, undersea).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `b019bbdc-3fdc-4a95-a630-057457614080_submission_2026-07-19T04_19_15.639Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
