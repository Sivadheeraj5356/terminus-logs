# Forty protection zones on the buried main (`zn-01` through `zn-40`, under /app/e

Submission: `594e5dd1-5ed1-4741-8555-7c45aafa7439`  
Slug: `forty-protection-zones-on-the-buried-main-zn-01-through-zn-4`  
Latest archive: `594e5dd1-5ed1-4741-8555-7c45aafa7439_submission_2026-07-18T15_58_17.444Z.zip`  
Revisions: 2

## Task summary

Forty protection zones on the buried main (`zn-01` through `zn-40`, under /app/environment/data) are due for fresh sacrificial anodes before the coating survey closes. For each zone you decide a count of anodes to string on it, and you decide how that count divides between the cheap rationed stock and the pricier expediter. Protection on a zone lasts as long as one of its anodes is still passing current at the end of the design life. Anodes corrode away on their own, one no faster for another failing beside it, so a zone strung with `n` anodes comes through the design life with probability `1 - (1 - p)^n`, in which `p` is that zone's own per-anode chance of lasting. The stringer shipped under /app/environment does the blunt thing and turns each zone's own retired-anode tally straight into a count, which leaves the single lowest zone short of `protection_floor`, so the sheet it prints does not pass. A passing rebuild has to lift every zone over the floor at once, and it has to earn that from the input as the program runs rather than from the shipped zone list, so the same compiled program still clears the floor when it is pointed at a different set of zones. The run is judged forward, against how the zones will hold over the service life still to come. Nobody hands you the true per-anode survival rate each zone will run at over that life; the score feeds those rates through `1 - (1 - p)^n` once the life has played out. The requirement is per-zone and simultaneous: all forty have to reach `protection_floor`, and it is the single lowest zone that the run is marked on, not...

Required artifacts include: `/app/environment/data`, `/app/environment`, `/app/environment/data/survival_log.csv`, `/app/environment/data/zones.csv`, `/app/environment/data/cp_policy.json`, `/app/environment/data/README.md`.

Author anonymous tagged this **hard** scientific-computing task (c, scientific-computing, reliability, estimation, optimization).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `594e5dd1-5ed1-4741-8555-7c45aafa7439_submission_2026-07-18T15_58_17.444Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
