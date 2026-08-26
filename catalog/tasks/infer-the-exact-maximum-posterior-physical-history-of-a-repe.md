# Infer the exact maximum-posterior physical history of a repeated-round planar st

Submission: `2ad50431-6057-47a4-9522-48ee134dfb71`  
Slug: `infer-the-exact-maximum-posterior-physical-history-of-a-repe`  
Latest archive: `2ad50431-6057-47a4-9522-48ee134dfb71_submission_2026-07-16T14_49_11.646Z.zip`  
Revisions: 7

## Task summary

Infer the exact maximum-posterior physical history of a repeated-round planar stabilizer experiment. The observed syndrome changes can arise from local Pauli occurrences, delayed signatures from earlier occurrences, a persistent readout frame, and latent thermal or control-line burst sources that emit across several rounds. Determine the complete minimum-energy likelihood manifold and its joint logical-coset degeneracy. A burst source is selected once for the whole experiment, not independently in each observation round. While active it can emit detector and logical signatures at multiple offsets, block named physical couplers, load each observed round, consume an experiment-wide exposure allowance, and charge both a global and sliding-window noise-family budget from its start round. Burst sources may also share exclusive physical origins. Local Pauli occurrences still obey cycle occupancy, same-cycle coupler exclusion, recovery exclusion, delayed detector tails, and global and sliding family bounds. Every proposed history must therefore resolve the readout frame, latent burst collection, and all round-local Pauli collections jointly.

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **hard** scientific-computing task (experimental-quantum-physics, stabilizer-measurements, latent-burst-noise, logical-cosets, exact-rational-likelihood).

Time estimates: expert ~720 min, junior ~1800 min.

Harbor timeouts: agent 1800s, verifier 300s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `2ad50431-6057-47a4-9522-48ee134dfb71_submission_2026-07-16T14_49_11.646Z.zip` is a task submission, not a Harbor job. 7 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
