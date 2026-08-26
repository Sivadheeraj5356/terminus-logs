# Thermal Radiometry Calibration Runbook
> Document revision 4.7 — internal lab use only.

## OBSOLETE — Legacy Profile 1 (superseded)
This section applied to retired camera models IR-1 through IR-3. Do not use 8-bit PNG decoding or filename ordering. Legacy flat-field before dark subtraction was deprecated in rev 2.1.
| Camera | Emissivity | Dark model |
|---|---|---|
| IR-1 | 0.1 | linear |
| IR-2 | 0.1 | linear |
| IR-3 | 0.1 | linear |

## OBSOLETE — Legacy Profile 2 (superseded)
This section applied to retired camera models IR-1 through IR-3. Do not use 8-bit PNG decoding or filename ordering. Legacy flat-field before dark subtraction was deprecated in rev 2.2.
| Camera | Emissivity | Dark model |
|---|---|---|
| IR-1 | 0.2 | linear |
| IR-2 | 0.2 | linear |
| IR-3 | 0.2 | linear |

## OBSOLETE — Legacy Profile 3 (superseded)
This section applied to retired camera models IR-1 through IR-3. Do not use 8-bit PNG decoding or filename ordering. Legacy flat-field before dark subtraction was deprecated in rev 2.3.
| Camera | Emissivity | Dark model |
|---|---|---|
| IR-1 | 0.3 | linear |
| IR-2 | 0.3 | linear |
| IR-3 | 0.3 | linear |

## OBSOLETE — Legacy Profile 4 (superseded)
This section applied to retired camera models IR-1 through IR-3. Do not use 8-bit PNG decoding or filename ordering. Legacy flat-field before dark subtraction was deprecated in rev 2.4.
| Camera | Emissivity | Dark model |
|---|---|---|
| IR-1 | 0.4 | linear |
| IR-2 | 0.4 | linear |
| IR-3 | 0.4 | linear |

## OBSOLETE — Legacy Profile 5 (superseded)
This section applied to retired camera models IR-1 through IR-3. Do not use 8-bit PNG decoding or filename ordering. Legacy flat-field before dark subtraction was deprecated in rev 2.5.
| Camera | Emissivity | Dark model |
|---|---|---|
| IR-1 | 0.5 | linear |
| IR-2 | 0.5 | linear |
| IR-3 | 0.5 | linear |

## OBSOLETE — Legacy Profile 6 (superseded)
This section applied to retired camera models IR-1 through IR-3. Do not use 8-bit PNG decoding or filename ordering. Legacy flat-field before dark subtraction was deprecated in rev 2.6.
| Camera | Emissivity | Dark model |
|---|---|---|
| IR-1 | 0.6 | linear |
| IR-2 | 0.6 | linear |
| IR-3 | 0.6 | linear |

## OBSOLETE — Legacy Profile 7 (superseded)
This section applied to retired camera models IR-1 through IR-3. Do not use 8-bit PNG decoding or filename ordering. Legacy flat-field before dark subtraction was deprecated in rev 2.7.
| Camera | Emissivity | Dark model |
|---|---|---|
| IR-1 | 0.7 | linear |
| IR-2 | 0.7 | linear |
| IR-3 | 0.7 | linear |

## Current Operating Profile (ACTIVE)
The active pipeline for IR-7, IR-9, and IR-12 cameras requires:

1. Decode all radiometry frames as **16-bit grayscale** PNG.
2. Order frames by manifest `timestamp_s`, never by filename.
3. Render calibration constants from the local Terraform module.
4. Convert counts to temperature using:
   `linearized = (raw - dark_offset(t) - per_pixel_dark) / flat_gain`
   `temperature_c = gain * linearized + offset + emissivity_correction`
   where `dark_offset(t) = dark_offset_base + dark_offset_rate * t`.
5. Apply static ROI mask AND dead-pixel mask, then **erode one pixel** before ROI stats.
6. Exclude saturated pixels (at or above saturation DN) and pixels below noise floor.
7. Report a **10% trimmed mean** temperature per frame ROI.
8. Fit cooling curve `T(t) = ambient + amplitude * exp(-k * t)` using weighted least squares in log-residual space after ambient subtraction.
9. Emit residual RMS, max absolute residual, half-life (`ln(2)/k`), start/end temperatures, and usable-pixel counts.
10. All JSON outputs must use deterministic key ordering.

### Mask and pixel inclusion semantics (ACTIVE)
Mask PNGs are 16-bit grayscale images aligned to the radiometry frame grid. A pixel is **mask-true** when its DN is **greater than or equal to 32768**.

- **ROI mask** (`manifest.calrefs.roi_mask`): mask-true pixels lie inside the analysis region.
- **Dead-pixel mask** (`manifest.calrefs.dead_pixel_mask`): use the file **as-is** (do not invert). Mask-true pixels are the **only** valid/non-dead pixels; mask-false pixels are excluded as dead. The shipped mask may be sparse; sparsity does not mean the polarity is inverted.
- **Combined mask** = logical AND of ROI mask-true and dead-pixel mask-true (valid) pixels.
- **Erosion**: apply binary erosion for `manifest.mask_erosion_px` iterations using an 8-connected neighborhood. After each iteration, a pixel survives only if it and all eight neighbors (including diagonals) are mask-true; image borders and excluded neighbors remove the pixel.
- **Usable pixel** (per frame): combined-and-eroded mask-true, not saturated (`raw >= manifest.saturation_dn`), and not below noise floor (`raw < manifest.noise_floor_dn`).
- **Flat gain**: per-pixel `flat_gain = flat_dn / 12000.0`; if flat DN is zero, use `1.0`.
- **mask_fraction** in frame summaries = fraction of pixels excluded by the final active mask (not saturation/noise filters).

### Cooling-curve fitting semantics (ACTIVE)
Per session, sort frames by manifest `timestamp_s` ascending, then `frame_id`.

- Build the fit sample from frames with at least one usable pixel. Each sample point is `(timestamp_s, trimmed_mean_c)` for that frame.
- **Trimmed mean**: sort usable pixel temperatures, remove `floor(n * manifest.trim_fraction)` values from each tail, average the remainder. Empty set yields `0.0`.
- **Ambient temperature** for the fit = `trimmed_mean_c` of the **last** sample point in timestamp order (the final usable frame).
- Fit `T(t) = ambient + amplitude * exp(-k * t)` with **weighted least squares in log-residual space**:
  - For each sample with `trimmed_mean_c > ambient`, let `y = trimmed_mean_c - ambient`, weight `w = 1 / (y + 1e-6)`, regress `log(y)` against `t`.
  - Discard samples where `y <= 0`.
  - Clamp `k` to be non-negative. If `k <= 1e-12`, set `half_life_s = 0`.
  - **Half-life** = `ln(2) / k` when `k > 1e-12`.
- **Residual metrics**: RMS and max absolute residual of `trimmed_mean_c` versus the fitted curve across all sample points in the session.
- **usable_frame_count** = frames with at least one usable pixel. **mean_usable_pixels** averages `usable_pixels` over usable frames only.
- **input_digest**: SHA256 over sorted relative file paths and raw bytes under the input directory (same algorithm as `/app/scripts/directory_digest.py`).

### Changelog overrides
- Rev 4.7: trimmed mean replaces simple mean (overrides §3.2 and §8.1).
- Rev 4.6: one-pixel mask erosion is mandatory (overrides §5.4 legacy no-erosion rule).
- Rev 4.5: Terraform emissivity correction restored (overrides §2.9 constant-only table).
- Rev 4.4: manifest timestamp ordering (overrides filename sort in §6.0).

### Camera constant tables (reference only — Terraform is authoritative)

#### cam-ir7
| Parameter | Example | Notes |
|---|---|---|
| gain | 0.04 | use module output |
| offset | -273 | use module output |
| emissivity_correction | 1.0 | use module output |
| dark_offset_base | 1800 | use module output |
| dark_offset_rate | 0.3 | use module output |

#### cam-ir9
| Parameter | Example | Notes |
|---|---|---|
| gain | 0.04 | use module output |
| offset | -273 | use module output |
| emissivity_correction | 1.0 | use module output |
| dark_offset_base | 1800 | use module output |
| dark_offset_rate | 0.3 | use module output |

#### cam-ir12
| Parameter | Example | Notes |
|---|---|---|
| gain | 0.04 | use module output |
| offset | -273 | use module output |
| emissivity_correction | 1.0 | use module output |
| dark_offset_base | 1800 | use module output |
| dark_offset_rate | 0.3 | use module output |

## Dark current drift monitoring
Paragraph 1 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 2 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 3 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 4 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 5 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 6 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 7 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 8 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 9 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 10 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 11 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 12 for Dark current drift monitoring: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.

## Flat-field uniformity checks
Paragraph 1 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 2 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 3 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 4 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 5 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 6 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 7 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 8 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 9 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 10 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 11 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 12 for Flat-field uniformity checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.

## ROI placement for cooling plates
Paragraph 1 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 2 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 3 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 4 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 5 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 6 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 7 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 8 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 9 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 10 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 11 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 12 for ROI placement for cooling plates: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.

## Lab humidity compensation (not used in IR-7 profile)
Paragraph 1 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 2 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 3 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 4 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 5 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 6 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 7 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 8 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 9 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 10 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 11 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 12 for Lab humidity compensation (not used in IR-7 profile): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.

## Export audit trail requirements
Paragraph 1 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 2 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 3 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 4 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 5 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 6 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 7 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 8 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 9 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 10 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 11 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 12 for Export audit trail requirements: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.

## PNG metadata tags (informational)
Paragraph 1 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 2 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 3 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 4 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 5 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 6 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 7 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 8 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 9 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 10 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 11 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 12 for PNG metadata tags (informational): operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.

## Session naming conventions
Paragraph 1 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 2 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 3 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 4 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 5 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 6 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 7 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 8 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 9 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 10 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 11 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 12 for Session naming conventions: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.

## Cooling curve QA thresholds
Paragraph 1 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 2 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 3 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 4 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 5 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 6 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 7 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 8 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 9 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 10 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 11 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 12 for Cooling curve QA thresholds: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.

## Dead pixel map maintenance
Paragraph 1 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 2 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 3 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 4 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 5 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 6 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 7 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 8 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 9 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 10 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 11 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 12 for Dead pixel map maintenance: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.

## Radiometric linearity spot checks
Paragraph 1 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 2 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 3 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 4 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 5 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 6 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 7 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 8 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 9 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 10 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 11 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
Paragraph 12 for Radiometric linearity spot checks: operators must cross-check manifest timestamps, verify reference frames are captured at stable temperature, and archive intermediate summaries. Example configurations for retired sessions are illustrative only and must not override the Current Operating Profile unless explicitly marked ACTIVE.
