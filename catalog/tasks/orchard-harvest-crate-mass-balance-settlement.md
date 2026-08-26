# # Orchard harvest crate mass-balance settlement

Submission: `02035d55-3b98-4031-b9f7-3fcf2af065cc`  
Slug: `orchard-harvest-crate-mass-balance-settlement`  
Latest archive: `02035d55-3b98-4031-b9f7-3fcf2af065cc_submission_2026-07-20T07_34_34.423Z.zip`  
Revisions: 8

## Task summary

Orchard pickup settlement on the HARVEST1 lane is failing metrology QA. The pick-balance driver reads newline-delimited capture rows (pick, tare, supersede, spoilage) from an input feed and writes a per-zone balance report under /app/output. Independent replay audits report mismatches across generation ordering, tare offset windows and gram-band thresholds, void and refusal cadence, capacity accounting, zone label identity, settlement tie precedence, stamp lineage, and checkpoint resume parity. The gram-conservation metrology model, checkpoint schema, digest preimages, and report fields are normative in /app/docs/harvest_rules.txt. Build and operator usage are in /app/docs/toolchain.txt.

Required artifacts include: `/app/output`, `/app/docs/harvest_rules.txt`, `/app/docs/toolchain.txt`, `/app/environment`.

Author anonymous tagged this **hard** scientific-computing task (metrology, mass-conservation, numerical-settlement, scientific-simulation, grade-classification, checkpoint-resume, deterministic-replay).

Time estimates: expert ~90 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `02035d55-3b98-4031-b9f7-3fcf2af065cc_submission_2026-07-20T07_34_34.423Z.zip` is a task submission, not a Harbor job. 8 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
