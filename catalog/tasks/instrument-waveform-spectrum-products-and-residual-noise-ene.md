# Instrument waveform spectrum products and residual noise-energy audits must be c

Submission: `b73344a5-0047-4e36-acf8-9ef65ac2bfb3`  
Slug: `instrument-waveform-spectrum-products-and-residual-noise-ene`  
Latest archive: `b73344a5-0047-4e36-acf8-9ef65ac2bfb3_submission_2026-07-18T10_53_15.797Z.zip`  
Revisions in Dropbox: 1

## Task summary

Instrument waveform spectrum products and residual noise-energy audits must be computed with a documented multi-level Haar discrete wavelet transform and level-dependent soft thresholding so lab engineers can certify numeric reconstruction energy against the MAD noise estimator. Using noisy traces under /app/data/traces/, versioned threshold policies under /app/data/threshold-policies/, and denoise settings under /app/data/denoise-config.json, transform each trace, apply soft thresholds on detail bands only, invert the Haar pyramid, and publish residual energy products. Stage intermediate products under /app/state/ as /app/state/trace-snapshot.json, /app/state/coeff-ledger.json, /app/state/coeff-pack.json, and /app/state/threshold-journal.json before writing /app/output/denoised-traces.json and /app/output/noise-audit.json. The orthonormal Haar pair, odd-length padding, and level clamp are in /app/docs/haar-dwt-model.md. MAD scale estimation, policy supersession, and soft-threshold rules are in /app/docs/soft-threshold-mad.md. Reconstruction energy, residual definitions, and output schemas are in /app/docs/reconstruction-energy.md. Staging field contracts are in /app/docs/staging-contract.md. Sealed coefficient provenance between decompose and export is in /app/docs/coeff-pack-seal.md. CLI modes ingest-traces, decompose-threshold, reconstruct-export, and version are in /app/docs/cli-surface.md.

Required artifacts include: `/app/data/traces/`, `/app/data/threshold-policies/`, `/app/data/denoise-config.json`, `/app/state/`, `/app/state/trace-snapshot.json`, `/app/state/coeff-ledger.json`, `/app/state/coeff-pack.json`, `/app/state/threshold-journal.json`.

Author rupesh1285 tagged this **hard** scientific-computing task (scientific-computing, haar-dwt, wavelet-denoise, soft-threshold, mad-estimator, instrument-trace).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `b73344a5-0047-4e36-acf8-9ef65ac2bfb3_submission_2026-07-18T10_53_15.797Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
