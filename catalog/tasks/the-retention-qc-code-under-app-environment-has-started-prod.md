# The retention QC code under `/app/environment` has started producing lineage-dep

Submission: `62937445-db90-42ef-81b9-b9f083e3bf6a`  
Slug: `the-retention-qc-code-under-app-environment-has-started-prod`  
Latest archive: `62937445-db90-42ef-81b9-b9f083e3bf6a_submission_2026-07-15T09_28_47.670Z.zip`  
Revisions: 1

## Task summary

The retention QC code under `/app/environment` has started producing lineage-dependent attestations. Results change with harmless shard layouts, default leave-one-run-out records disagree with isolated runs, and some local edits alter unrelated records. Repair the Go source code under `/app/environment` so it follows `/app/environment/docs/ra_contract.md` for CELL/3 identity, normalized coordinates, model fitting, finite-sample coverage, lineage, canonical closure, and atomic errors. The normal command is `/app/environment/tools/ra_run --emit-attestation /app/output/attestation_pack.json`. It must regenerate the JSON from the selected input tree; editing the output by hand is not sufficient. The command options, record shape, field types, and sorting rules are in the contract.

Required artifacts include: `/app/environment`, `/app/environment/docs/ra_contract.md`, `/app/environment/tools/ra_run`, `/app/output/attestation_pack.json`.

Author anonymous tagged this **hard** scientific-computing task (go, bash, proteomics, cross-validation, lineage, attestation).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1200s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `62937445-db90-42ef-81b9-b9f083e3bf6a_submission_2026-07-15T09_28_47.670Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
