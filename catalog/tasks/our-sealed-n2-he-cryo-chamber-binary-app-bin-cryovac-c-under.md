# Our sealed N2/He cryo chamber binary `/app/bin/cryovac` (C under `/app/src`) dri

Submission: `97512bcf-0045-4a89-959b-a75728516d51`  
Slug: `our-sealed-n2-he-cryo-chamber-binary-app-bin-cryovac-c-under`  
Latest archive: `97512bcf-0045-4a89-959b-a75728516d51_submission_2026-07-19T05_03_08.827Z.zip`  
Revisions in Dropbox: 6

## Task summary

Our sealed N2/He cryo chamber binary `/app/bin/cryovac` (C under `/app/src`) drifted from the plant model. Bring it back in line with `/app/docs/thermo-model.md` and `/app/docs/schema.json`, and restore `/app/config/species.json` plus `/app/config/chamber.toml` to the normative plant constants and solver limits that doc lists (N2 `T_freeze`/`T_thaw`/`film_site_beta`, and `max_solver_iters`/`ads_tol`/`cond_tol`). Leave the docs themselves alone. The sim must use free-volume Van der Waals pressure with a Lorentz–Berthelot `sqrt(a1·a2)` cross term and condensate displacing `V_free` (with `vmin_frac` floor); fugacity-driven competitive Langmuir with condensate footprint cutting `n_sites_eff`; sticky any-leg/universal calibration that survives short higher-`seq` overlays while leg-gated rows always fresh-resolve; `requires_prev_seq` exact predecessor gating; thermal legs descend/ascend with equal-T reuse of the prior leg; freeze when `T <= T_freeze` with condensate present and thaw only when `T >= T_thaw`; thaw-station N2 wall-hold; He never in bulk film; and a multi-pass sorption→condensation fixed point per station. CLI is `--profile` / `--calibration` / `--out` / `--volume` (defaults `/app/data/profiles/n2_he_cooldown.json`, `/app/data/calibration/sorption_cal.ndjson`, `/app/vacuum_simulation.json`, `0.012` m³). Unknown, incomplete, or repeated flags and non-positive volume are fatal (exit 2, empty stdout). Success is exit 0. Reported `p_total` must track the free-gas EOS on `V_free` within about 0.1%, mole ledgers must close, calibration must be file-order and CRLF...

Required artifacts include: `/app/bin/cryovac`, `/app/src`, `/app/docs/thermo-model.md`, `/app/docs/schema.json`, `/app/config/species.json`, `/app/config/chamber.toml`, `/app/data/profiles/n2_he_cooldown.json`, `/app/data/calibration/sorption_cal.ndjson`.

Author anonymous tagged this **hard** scientific-computing task (scientific-computing, thermodynamics, van-der-waals, sorption, cryogenics, phase-transition).

Time estimates: expert ~180 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `97512bcf-0045-4a89-959b-a75728516d51_submission_2026-07-19T05_03_08.827Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
