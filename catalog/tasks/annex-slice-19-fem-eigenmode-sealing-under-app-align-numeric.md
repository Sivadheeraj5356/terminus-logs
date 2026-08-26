# Annex-slice-19 FEM eigenmode sealing under `/app`. Align numerical authorities a

Submission: `23e9883f-fddc-451d-9d26-b18dd57b1e56`  
Slug: `annex-slice-19-fem-eigenmode-sealing-under-app-align-numeric`  
Latest archive: `23e9883f-fddc-451d-9d26-b18dd57b1e56_submission_2026-07-15T11_49_38.969Z.zip`  
Revisions in Dropbox: 5

## Task summary

Annex-slice-19 FEM eigenmode sealing under `/app`. Align numerical authorities and peel timing under `/app/data` so panels conserve. Clear stale tip, seal.bind, and WAL under `/app/data/ms_store`, then rematerialize `/app/output/invariant_proof_log.json` via `/app/scripts/proof_run.sh`. Treat mode_seal as sealed. Coupled residual subtracts weight*excit*(gain*fringe + coupling*gain_next*fringe_next) from (omega_obs - omega_ref) with next cycling M1-M4. Digests follow `/app/scripts/digest_encoding.py`. Arms permute_modes, reverse_locale_bands, and cascade_compose must match the full digest; chain_digest binds that quartet.

Required artifacts include: `/app/data`, `/app/data/ms_store`, `/app/output/invariant_proof_log.json`, `/app/scripts/proof_run.sh`, `/app/scripts/digest_encoding.py`.

Author anonymous tagged this **hard** scientific-computing task (fem, eigenmode, calibration, metamorphic, epoch-fuse, coupling).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `23e9883f-fddc-451d-9d26-b18dd57b1e56_submission_2026-07-15T11_49_38.969Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
