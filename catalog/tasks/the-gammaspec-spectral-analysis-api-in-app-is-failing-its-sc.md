# The GammaSpec spectral-analysis API in `/app` is failing its scientific audit. S

Submission: `709d69b2-8f2a-400c-be33-15929f107e3e`  
Slug: `the-gammaspec-spectral-analysis-api-in-app-is-failing-its-sc`  
Latest archive: `709d69b2-8f2a-400c-be33-15929f107e3e_submission_2026-07-08T11_02_35.602Z.zip`  
Revisions in Dropbox: 1

## Task summary

The GammaSpec spectral-analysis API in `/app` is failing its scientific audit. Start with `/app/docs/00_gammaspec_contract.md`; it is the short normative map for the numerical wire contract. Treat `/app/docs/gammaspec_methods.md` as the full GammaSpec methods source when you need lab rationale or requirement IDs, and use `/app/audit/strace-gammaspec.log` plus `/app/audit/lsof-gammaspec.txt` as operational evidence. Keep the TypeScript/Express wrapper runnable from `/app` with `npm run build` and `npm start`; `/health` should return JSON with `ok: true`. Patch the scientific behavior exposed by `POST /fit`, `POST /bootstrap`, `POST /batch-fit`, `POST /diagnostics`, and `POST /isotope-screen` so each endpoint exactly matches that contract. The routes must return HTTP 400 JSON for malformed numeric inputs, timing/background errors, unknown isotopes, invalid bootstrap iterations, and non-integer seeds. The fixed service must apply the documented calibration, normalization, fitting, uncertainty, quality-flag, deterministic bootstrap, sorted batch, compact-output, diagnostics, candidate-screening, and calibration-resource rules without leaking file descriptors across repeated requests.

Required artifacts include: `/app/docs/00_gammaspec_contract.md`, `/app/docs/gammaspec_methods.md`, `/app/audit/strace-gammaspec.log`, `/app/audit/lsof-gammaspec.txt`, `/app/output/compliance_matrix.json`, `/app/`, `/app/docs/gammaspec_methods.md#`.

Author anonymous tagged this **hard** scientific-computing task (express, typescript, weighted-least-squares, strace, bootstrap, batch-api).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1500.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `709d69b2-8f2a-400c-be33-15929f107e3e_submission_2026-07-08T11_02_35.602Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
