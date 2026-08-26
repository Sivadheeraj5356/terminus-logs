# The dye-transfer restoration desk under `/app/environment` regenerates sealed co

Submission: `fbeecdda-057f-4aca-88ba-9a92c165cd1c`  
Slug: `the-dye-transfer-restoration-desk-under-app-environment-rege`  
Latest archive: `fbeecdda-057f-4aca-88ba-9a92c165cd1c_submission_2026-07-15T16_55_33.775Z.zip`  
Revisions in Dropbox: 3

## Task summary

The dye-transfer restoration desk under `/app/environment` regenerates sealed continuum artifacts for multi-reel archival prints, but regenerated bundles disagree with the published restoration math: splice verdicts and digests drift across JSON, CSV, and summary logs; re-running the same case under a hotter, wetter booth climate advances epoch while density-derived gaps stay pinned to the prior climate band. Binaries under `/app/bin/` are built from `/app/environment`. Produce correct regenerated artifacts through those binaries, including `/app/output/continuum_report.json`. Static hand-written outputs are insufficient. Public schemas, formulas, CLI usage, companion binary names, and the full artifact set are documented in `/app/environment/docs/overview.md`. Invalid case input must exit nonzero with stderr beginning `invalid continuum case input:` and must not create `/app/output/continuum_report.json`. Bundled cases are under `/app/environment/data/cases/`.

Required artifacts include: `/app/environment`, `/app/bin/`, `/app/output/continuum_report.json`, `/app/environment/docs/overview.md`, `/app/environment/data/cases/`.

Author anonymous tagged this **hard** scientific-computing task (dye-transfer, densitometry, archival-film, go, rust).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `fbeecdda-057f-4aca-88ba-9a92c165cd1c_submission_2026-07-15T16_55_33.775Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
