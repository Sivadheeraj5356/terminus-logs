# specification_archaeology

Submission: `4018aa09-b19d-47fe-a6cd-cc1aed10ad53`  
Slug: `specification-archaeology`  
Latest archive: `4018aa09-b19d-47fe-a6cd-cc1aed10ad53_submission_2026-07-15T10_45_53.627Z.zip`  
Revisions: 1

## Task summary

Security engineering needs a defensible containment decision for four incident cases. The evidence under `/app/environment/evidence`, case overlays under `/app/environment/cases`, and authority documents under `/app/environment/authorities` are the complete record. Reconcile them using the public rules in those documents; filenames and record order carry no authority. Output-only work is allowed; no supplied application is broken. Source code under `/app/environment` must be fixed by implementing the interface in `/app/environment/adjudicator.py`. The verifier removes `/app/out` and runs `/app/environment/run.sh`; that command must regenerate, for every profile, `/app/out/<profile>/trust_assessment.json`, `/app/out/<profile>/containment_plan.json`, and `/app/out/<profile>/decision_commitment.bin`. Hand-written outputs that cannot be regenerated are insufficient. Execution is offline and must use only the Python standard library.

Required artifacts include: `/app/environment/evidence`, `/app/environment/cases`, `/app/environment/authorities`, `/app/environment`, `/app/environment/adjudicator.py`, `/app/out`, `/app/environment/run.sh`, `/app/out/`.

Author anonymous tagged this **hard** security task (pki, incident-response, trust-graph, policy-adjudication, containment).

Time estimates: expert ~180 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `4018aa09-b19d-47fe-a6cd-cc1aed10ad53_submission_2026-07-15T10_45_53.627Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
