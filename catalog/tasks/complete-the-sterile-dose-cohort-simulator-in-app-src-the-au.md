# Complete the sterile-dose cohort simulator in `/app/src`. The authoritative scie

Submission: `48be4670-92a1-4d47-9dd0-f56a6c32920a`  
Slug: `complete-the-sterile-dose-cohort-simulator-in-app-src-the-au`  
Latest archive: `48be4670-92a1-4d47-9dd0-f56a6c32920a_submission_2026-07-14T06_59_31.527Z.zip`  
Revisions: 3

## Task summary

Complete the sterile-dose cohort simulator in `/app/src`. The authoritative scientific and file contract is `/app/docs/model_contract.md`. It combines time-dependent assay decay, correlated uncertainty groups, substitute materials, discrete vial consumption, chronological inventory events, repeated priming cycles, open-vial stability episodes with post-opening potency decay and uncertainty growth, order budgets, bounded workload limits, and a cohort-wide lexicographic allocation objective. The implementation must apply the contract to any valid input directory, produce the exact deterministic `amberglass.v6` report requested by the caller, and fail closed on invalid input while removing a stale requested output. LF and CRLF CSV files are valid, whitespace-only physical records are ignored for parsing while remaining part of the raw-byte input digest, and `prime_grams` may be zero. Keep `/app/src` as an offline-buildable Go module. The verifier compiles the current source once with its own isolated Go command into the Linux ELF executable `/app/bin/amberglass` and reuses that binary for every case. Run it as `/app/bin/amberglass <input_dir> <output_json>`; success is silent and writes only the requested JSON file. The verifier uses additional valid inputs that are not bundled with the task and checks coupled assay, chronological event replay, open-age degradation, uncertainty, vial-episode, allocation, schema, digest, ordering, determinism, workload-boundary, identifier, and stale-output behavior. Compute from the supplied files rather than hardcoding fixture values or...

Required artifacts include: `/app/src`, `/app/docs/model_contract.md`, `/app/bin/amberglass`.

Author anonymous tagged this **hard** scientific-computing task (go, robust-optimization, assay-decay, vial-packing, sha256).

Time estimates: expert ~420 min, junior ~780 min.

Harbor timeouts: agent 1800.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `48be4670-92a1-4d47-9dd0-f56a6c32920a_submission_2026-07-14T06_59_31.527Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
