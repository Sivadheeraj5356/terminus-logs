# Instrument waveform spectrum products and residual noise-energy audits must be c

- **UUID:** `b73344a5-0047-4e36-acf8-9ef65ac2bfb3`
- **Slug:** `instrument-waveform-spectrum-products-and-residual-noise-ene`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Instrument waveform spectrum products and residual noise-energy audits must be computed with a documented multi-level Haar discrete wavelet transform and level-dependent soft thresholding so lab engineers can certify numeric reconstruction energy against the MAD noise estimator. Using noisy traces under /app/data/traces/, versioned threshold policies under /app/data/threshold-policies/, and denoise settings under /app/data/denoise-config.json, transform each trace, apply soft thresholds on detail bands only, invert the Haar pyramid, and publish residual energy products.

Stage intermediate products under /app/state/ as /app/state/trace-snapshot.json, /app/state/coeff-ledger.json, /app/state/coeff-pack.json, and /app/state/threshold-journal.json before writing /app/output/denoised-traces.json and /app/output/noise-audit.json. The orthonormal Haar pair, odd-length padding, and level clamp are in /app/docs/haar-dwt-model.md.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
