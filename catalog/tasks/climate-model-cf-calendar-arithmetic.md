# # Climate model CF calendar arithmetic

Submission: `dcbfce51-fa5b-4d62-853f-ef64646cdd8f`  
Slug: `climate-model-cf-calendar-arithmetic`  
Latest archive: `dcbfce51-fa5b-4d62-853f-ef64646cdd8f_submission_2026-07-20T06_14_19.400Z.zip`  
Revisions in Dropbox: 1

## Task summary

Numerical time axes in climate and earth-system models follow CF conventions. An encoded day count must decode to the same calendar-qualified year-month-day under its declared calendar and units origin: 360_day years use twelve 30-day months; noleap years keep February at 28 days; Gregorian leap-year rules apply only when that calendar is declared. Interval bounds and monthly climatological bins must use that same calendar arithmetic, not fixed Unix-day widths. The toolkit under `/app` must preserve those numerical instants when climate simulation members with different units origins are placed on one axis, including when an earlier committed prefix under `/data/segments/` has already been retired. Bring `/app` into compliance with `/app/docs/time-contract.md` and `/app/docs/CLIMATE_AXIS.md` using working state under `/var/lib/climconvert/climate_axis/` and surviving members under `/data/segments/`. Treat the behavioral guarantees and report contract in `/app/docs/CLIMATE_AXIS.md` as requirements, not background context.

Required artifacts include: `/app/docs/time-contract.md`, `/app/docs/CLIMATE_AXIS.md`, `/output/archive.ccf`, `/output/archive-monthly.ccf`, `/output/climate-axis-report.json`, `/app/docs/FORMATS.md`.

Author anonymous tagged this **hard** scientific-computing task (climate-modeling, calendar-arithmetic, cf-conventions, 360-day-calendar, noleap, climatological-bins).

Time estimates: expert ~180 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `dcbfce51-fa5b-4d62-853f-ef64646cdd8f_submission_2026-07-20T06_14_19.400Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
