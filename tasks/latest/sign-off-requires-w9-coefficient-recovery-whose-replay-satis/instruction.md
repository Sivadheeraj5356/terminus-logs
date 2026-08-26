Sign-off requires w9 coefficient recovery whose replay satisfies every tolerance class in `/app/docs/w9_rules.md`. Holdout dynamics under `/app/data/v9/segments/` currently disagree with q9 profile calibration under `/app/data/q9/`.

Update modules under `/app/environment` so `node /app/environment/z9/w9_once.js` regenerates `/app/out/coeff_v9.json` and `/app/out/trace_v9.log`. Field names blend_weights, link_scalar, forcing, bands, profiles, p7_rms, p8_rms, phase_lag, segment_a_rms_x, segment_a_rms_y, segment_b_rms_x, segment_b_rms_y, and band_row are defined in the contract doc. Class E band checks compare replay slots against the read-only sidecar table; holdout forward agreement reports per-segment rms_x and rms_y prey/predator RMS statistics in trace_v9. Consecutive replays must yield byte-identical artifacts. Static writes to either output path are insufficient.

Do not modify `/app/data/v9/segments/` or `/tests/`.
