# Sign-off requires w9 coefficient recovery whose replay satisfies every tolerance

- **UUID:** `62c01bd9-0317-4cad-8a76-ef95efdbaae7`
- **Slug:** `sign-off-requires-w9-coefficient-recovery-whose-replay-satis`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Sign-off requires w9 coefficient recovery whose replay satisfies every tolerance class in `/app/docs/w9_rules.md`. Holdout dynamics under `/app/data/v9/segments/` currently disagree with q9 profile calibration under `/app/data/q9/`.

Update modules under `/app/environment` so `node /app/environment/z9/w9_once.js` regenerates `/app/out/coeff_v9.json` and `/app/out/trace_v9.log`. Field names blend_weights, link_scalar, forcing, bands, profiles, p7_rms, p8_rms, phase_lag, segment_a_rms_x, segment_a_rms_y, segment_b_rms_x, segment_b_rms_y, and band_row are defined in the contract doc.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
