# w9 replay contract

## 1. Replay command

`node /app/environment/z9/w9_once.js`

Symlink alias: `node /app/z9/w9_once.js`

Writes `/app/out/coeff_v9.json` and `/app/out/trace_v9.log`.

## 2. coeff_v9.json schema

```json
{
  "blend_weights": {"p7": number, "p8": number},
  "link_scalar": number,
  "forcing": {"omega_hat": number, "phase0": number},
  "bands": [{"row_ix": int, "slot_a": number, "slot_b": number, "slot_c": number, "slot_d": number}, ...],
  "profiles": {"p7_rms": number, "p8_rms": number}
}
```

## 3. trace_v9.log keys

One `key=value` per line (numbers in decimal):

- `p7_rms`, `p8_rms`: profile errors against q9 calibration vectors (class A)
- `link_scalar`: weighted RMS invariant (section 4)
- `phase_lag`: equals `phase0` from forcing estimate (class B)
- `seasonal_amp_p7`, `seasonal_amp_p8`: drive amplitudes (class B ceiling 0.2)
- `trough_depth_b` means minimum prey abundance on segment B (class C floor 0.5)
- `peak_height_b` means maximum predator abundance on segment B (class C ceiling 3.5)
- `envelope_skew` means segment A range divided by mean abundance (class B ceiling 2.0)
- `shift_metric` means absolute join gap between segment A tail and segment B head (class C)
- `log1p_restore_err` means inverse log1p map error on segment B trough (class D)
- `coupling_sign`: m7 polarity (1 or -1)
- `segment_a_rms_x`, `segment_a_rms_y`: prey and predator RMS on segment A holdout columns (class B)
- `segment_b_rms_x`, `segment_b_rms_y`: prey and predator RMS on segment B holdout columns (class B)
- `band_row_<N>_slot_a`..`slot_d` means rolling-window band statistics for row N (class E)

The `profiles` object in coeff_v9 means the nested p7_rms and p8_rms snapshot written beside blend weights.

Log keys map to coeff band columns: `slot_a`..`slot_d` on row N.

## 4. Scalar link invariant

`link_scalar = blend_weights.p7 * p7_rms + blend_weights.p8 * p8_rms`

Must hold in both coeff snapshot and trace log after replay.

## 5. Tolerance classes

| Class | metric family | bound |
|-------|---------------|-------|
| A | profile RMS (`p7_rms`, `p8_rms`) | 0.08 |
| B | envelope (`phase_lag`, `seasonal_amp_*`, `envelope_skew`) and v9 forward segment RMS | 0.12; amp ceiling 0.2; skew ceiling 2.0 |
| C | holdout extrema (`trough_depth_b`, `peak_height_b`, `shift_metric`) | 0.18; trough floor 0.5; peak ceiling 3.5 |
| D | transform restore (`log1p_restore_err`) | 0.02 |
| E | band table slots in coeff and trace | 0.0005 per slot |

Contract replay targets are numeric outputs of a converged replay pipeline aligned with sections 4 through 12. Agents reach them by calibrating environment modules and re-running replay, not by matching hidden literals.

## 6. Blend weight bounds

From `w9_config.toml`: each weight in [0.2, 0.8] and p7+p8 weights sum to 1.0 within 1e-6. Coupling polarity uses `coupling_sign` equals 1.0.

## 7. v9 segment agreement

Forward RK4 replay using the calibrated integrator must match held-out columns in `/app/data/v9/segments/segment_a.csv` and `segment_b.csv` within class B RMS bounds. Segment A aligns with integration samples starting at index 40; segment B at index 120. Compare prey (`u0`) and predator (`u1`) columns separately via per-segment `rms_x` and `rms_y` summary statistics. Replay writes `segment_a_rms_x`, `segment_a_rms_y`, `segment_b_rms_x`, and `segment_b_rms_y` into trace_v9 for contract comparison.

## 8. Regen idempotence

The fit runner may wipe `/app/out/` during regen. Re-running the replay command must reproduce byte-identical `/app/out/coeff_v9.json` and `/app/out/trace_v9.log` artifacts across consecutive replays.

## 9. Extension ODE

Two-compartment dynamics with optional m7 term on the first compartment and sinusoidal drive. q9 CSV stores transformed u0 (log1p with bias) and u1. v9 segments store physical abundances. Driver parameters and integration length are defined in the fit runner and config.

## 10. Band row semantics

Band rows expose `row_ix`, `slot_a`, `slot_b`, `slot_c`, and `slot_d` in coeff_v9 and mirrored `band_row_<N>_slot_*` keys in trace_v9. The fit runner materializes exactly 66 rows during replay. Windowing and slot statistics are implemented in the fit runner trajectory loop. Class E comparisons use the read-only sidecar table at `/app/ref/sidecar_table.csv` baked during image build from contract replay.

## 11. Profile RMS (class A)

`p7_rms` and `p8_rms` come from profile preprocessing on `/app/data/q9/p7_traces.csv` and `p8_traces.csv`. Calibration divisors and blend policy are defined in the profile preprocessing stage. The nested `profiles` object and trace keys must agree.

## 12. Forcing and band derivation

Forcing (`omega_hat`, `phase0`, `phase_lag`) is estimated from the p7 residual series via `fit_q4` in the forcing stage. Band statistics are derived from RK4 integration windows in the fit runner. Seasonal amplitudes in trace follow the driver amp scaled by profile weights. Segment and transform trace metrics (`trough_depth_b`, `peak_height_b`, `envelope_skew`, `shift_metric`, `log1p_restore_err`, `coupling_sign`) are computed in the fit runner from v9 segments and the state inverse map.
