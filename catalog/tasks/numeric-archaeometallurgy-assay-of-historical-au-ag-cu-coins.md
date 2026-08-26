# Numeric archaeometallurgy assay of historical Au–Ag–Cu coins must recover physic

Submission: `a6eb7662-4801-4f0b-914c-14e07cc91a76`  
Slug: `numeric-archaeometallurgy-assay-of-historical-au-ag-cu-coins`  
Latest archive: `a6eb7662-4801-4f0b-914c-14e07cc91a76_submission_2026-07-16T13_58_26.614Z.zip`  
Revisions in Dropbox: 6

## Task summary

Numeric archaeometallurgy assay of historical Au–Ag–Cu coins must recover physically valid bulk alloy mass fractions from non-destructive bulk-density and surface XRF measurements under a thermodynamic volume-additive mixing model, including full uncertainty-propagated feasible composition regions and inconsistency flags when density and corrected XRF bounds have empty intersection. Using the coin catalog at /app/data/coins.json, pure-metal reference densities at /app/data/metal-densities.json, surface-enrichment model table at /app/data/enrichment-models.json, and assay policy at /app/data/assay-config.json, evaluate each coin with the documented volume-additive mixing rule (or the supplied non-ideal correction term when a coin requests it), form the density-constraint band in composition space, apply the directional silver-bloom / copper-depletion surface-enrichment correction using each coin's own enrichment model parameters, intersect the density band with the corrected XRF bulk bound, and classify coins whose measurements admit no overlapping feasible region as measurement-inconsistent. Persist the authoritative assay snapshot at /app/state/assay-snapshot.json. From that snapshot alone publish /app/output/composition-results.json (per-coin feasible region bounds or inconsistency / insufficient-data status), /app/output/derivation-trace.json (density band, corrected XRF bound, and intersection detail), /app/output/inconsistent-coins.json, and /app/output/audit.json. Normative mixing, density-band, surface-enrichment, intersection, missing-data, snapshot, results,...

Required artifacts include: `/app/data/coins.json`, `/app/data/metal-densities.json`, `/app/data/enrichment-models.json`, `/app/data/assay-config.json`, `/app/state/assay-snapshot.json`, `/app/output/composition-results.json`, `/app/output/derivation-trace.json`, `/app/output/inconsistent-coins.json`.

Author rupesh1285 tagged this **hard** scientific-computing task (scientific-computing, archaeometallurgy, numismatics, alloy-density, xrf, feasibility-region).

Time estimates: expert ~180 min, junior ~420 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `a6eb7662-4801-4f0b-914c-14e07cc91a76_submission_2026-07-16T13_58_26.614Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
