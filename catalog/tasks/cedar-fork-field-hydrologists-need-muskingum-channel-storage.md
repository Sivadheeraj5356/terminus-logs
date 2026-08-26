# Cedar Fork field hydrologists need Muskingum channel-storage routing of each flo

Submission: `fdf2a9e0-9794-46f9-b759-4a2c0cbdcc9c`  
Slug: `cedar-fork-field-hydrologists-need-muskingum-channel-storage`  
Latest archive: `fdf2a9e0-9794-46f9-b759-4a2c0cbdcc9c_submission_2026-07-19T07_13_03.607Z.zip`  
Revisions in Dropbox: 2

## Task summary

Cedar Fork field hydrologists need Muskingum channel-storage routing of each flood wave down a dendritic channel network: the peak discharge (m³/s), the time-to-peak (h), and the outflow hydrograph (m³/s) at every admitted channel reach. Each reach stores and delays its flow by a storage time K (hours) and a weighting factor X in [0, 0.5], and the network shares a routing step dt_hours and an admission floor peak_min_cms on the rounded peak discharge. A storage pass marches an outflow series O[t] from the reach effective inflow I[t] through the Muskingum recurrence O[t] = C0·I[t] + C1·I[t−1] + C2·O[t−1], with the weights C0, C1, C2 formed from K, X, and dt_hours. The reach effective inflow gathers its headwater boundary series or the routed outflow arriving from the reaches above it, together with any lateral inflow marks; the peak discharge is the largest rounded outflow and the time-to-peak is the step index of that first maximum times dt_hours. The basin geometry, each reach K and X, the routing step, the admission floor, and the event inflow marks arrive packed in a little-endian binary field survey at `/app/data/survey.bin`. Field desk context is in `/app/data/field_protocol.md`, and the survey byte layout, the Muskingum weight formulas, the half-even three-decimal rounding rule, and the quantity field and record order are in `/app/docs/channel_hydrograph_contract.md`. How many storage passes each reach is advanced through, the timing with which upstream reach outflow and lateral marks enter a reach effective inflow, the exact peak-floor boundary, and how a reach...

Required artifacts include: `/app/data/survey.bin`, `/app/data/field_protocol.md`, `/app/docs/channel_hydrograph_contract.md`, `/app/calibration/`, `/app/bin/channel-route`.

Author anonymous tagged this **hard** scientific-computing task (hydrology, muskingum, channel-storage, peak-discharge, channel-routing).

Time estimates: expert ~150 min, junior ~360 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `fdf2a9e0-9794-46f9-b759-4a2c0cbdcc9c_submission_2026-07-19T07_13_03.607Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
