# The lab under `/app` exercises offline integrity measurement and appraisal enfor

Submission: `e3085bc3-fe09-4d0e-8814-9fad0d5e396a`  
Slug: `the-lab-under-app-exercises-offline-integrity-measurement-an`  
Latest archive: `e3085bc3-fe09-4d0e-8814-9fad0d5e396a_submission_2026-07-21T04_08_56.413Z.zip`  
Revisions in Dropbox: 2

## Task summary

The lab under `/app` exercises offline integrity measurement and appraisal enforcement across split policy authorities. A Go lowering pass resolves the authority pin at `/app/data/authority/pin.json` under `/app/data/authority/`, materializes attachments from the resolved policy bundle (production attachments also live under `/app/data/policy.json`) into `/app/output/program.json`, and a Rust replay worker records `/app/output/read_traces.json` and `/app/output/measure_log.json`. A reconcile pass rolls manifest attestation into `/app/output/integrity_report.json`. Rebuild with `bash /app/scripts/build.sh`. Enforcement contract: `/app/docs/MODEL.md`. Report layout: `/app/schemas/report.schema.md`. Attestation roll-up: `/app/docs/ATTESTATION_CHAIN.md`. Authority split: `/app/docs/TRUST_LAYERS.md`. The deployed authorities disagree with the model. Some measure-only bands still look clean. Other reads finish without digest evidence they should carry, with appraisal results that disagree with `/app/data/manifest.json`, with digest rows keyed incorrectly, or with enforcement applied where no attachment authorizes it.

Required artifacts include: `/app/data/authority/pin.json`, `/app/data/authority/`, `/app/data/policy.json`, `/app/output/program.json`, `/app/output/read_traces.json`, `/app/output/measure_log.json`, `/app/output/integrity_report.json`, `/app/scripts/build.sh`.

Author anonymous tagged this **hard** security task (integrity, access-control, policy-reconciliation, authority-split, ima).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `e3085bc3-fe09-4d0e-8814-9fad0d5e396a_submission_2026-07-21T04_08_56.413Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
