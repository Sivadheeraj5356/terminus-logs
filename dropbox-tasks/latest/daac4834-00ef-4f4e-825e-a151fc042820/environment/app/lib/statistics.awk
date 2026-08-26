# Spectral statistics with intentional scientific defects
function compute_statistics(    err, p, mean, px) {
  err = build_wavelengths()
  if (err != "") return err
  build_mask_set()
  # BUG: constant baseline mean over all pixels including masks
  mean = 0
  for (p = 1; p <= frame_sample_count; p++) mean += samples[p]
  mean /= frame_sample_count
  baseline_mean = mean

  # BUG: pixel-space centroid with plain sum intensity
  sumw = 0
  sumpx = 0
  stat_intensity = 0
  for (p = 1; p <= frame_sample_count; p++) {
    res = samples[p] - baseline_mean
    if (p >= cfg_baseline1_lo + 1 && p <= cfg_baseline1_hi + 1) {
      baseline_side_res[p] = res
    }
    if (p >= cfg_baseline2_lo + 1 && p <= cfg_baseline2_hi + 1) {
      baseline_side_res[p] = res
    }
    lam = wavelength[p]
    if (lam >= cfg_peak_lo && lam <= cfg_peak_hi) {
      w = (res > 0) ? res : 0
      sumw += w
      sumpx += (p - 1) * w
      stat_intensity += w
    }
  }
  if (sumw > 0) {
    px_centroid = sumpx / sumw
    stat_centroid_nm = wavelength[int(px_centroid) + 1]
  } else {
    stat_centroid_nm = cfg_reference_nm
  }
  # BUG: population std (divide by n)
  n = 0; mean = 0; var = 0
  for (p in baseline_side_res) { n++; mean += baseline_side_res[p] }
  if (n > 0) {
    mean /= n
    for (p in baseline_side_res) var += (baseline_side_res[p] - mean) ^ 2
    stat_noise = sqrt(var / n)
  } else {
    stat_noise = 0
  }
  stat_drift_pm = (stat_centroid_nm - cfg_reference_nm) * 1000.0
  return ""
}

function build_mask_set(    i) {
  delete mask_set
  for (i = 1; i <= mask_count; i++) mask_set[mask_list[i]] = 1
}
