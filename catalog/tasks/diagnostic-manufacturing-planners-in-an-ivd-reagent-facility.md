# Diagnostic manufacturing planners in an IVD reagent facility must analyze availa

Submission: `e790d597-2ab7-423d-972d-99b80d282b95`  
Slug: `diagnostic-manufacturing-planners-in-an-ivd-reagent-facility`  
Latest archive: `e790d597-2ab7-423d-972d-99b80d282b95_submission_2026-07-13T06_56_42.082Z.zip`  
Revisions in Dropbox: 5

## Task summary

Diagnostic manufacturing planners in an IVD reagent facility must analyze available reagent lots against batch concentration specifications, produce the least-cost feasible blend per specification under linear constraint satisfaction with shared lot inventory depletion across the batch, and deliver a dual-price feasibility certificate with complementary slackness closure for quality audit. Implement the blendcert least-cost blend and dual-price feasibility certificate workflow under /app per the cited contracts. Deliver the blend feasibility workflow per /app/docs/overview.md, /app/docs/concentration-bands.md, /app/docs/lot-inventory-contract.md, /app/docs/blend-solve-contract.md, /app/docs/dual-price-certificate.md, /app/docs/gap-bound-complementary-slackness.md, /app/docs/blend-feasibility-cert-contract.md, and /app/docs/blend-ledger-contract.md.

Required artifacts include: `/app/docs/overview.md`, `/app/docs/concentration-bands.md`, `/app/docs/lot-inventory-contract.md`, `/app/docs/blend-solve-contract.md`, `/app/docs/dual-price-certificate.md`, `/app/docs/gap-bound-complementary-slackness.md`, `/app/docs/blend-feasibility-cert-contract.md`, `/app/docs/blend-ledger-contract.md`.

Author anonymous tagged this **hard** scientific-computing task (reagent-blending, ivd, linear-programming, dual-pricing, feasibility-certificate).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `e790d597-2ab7-423d-972d-99b80d282b95_submission_2026-07-13T06_56_42.082Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
