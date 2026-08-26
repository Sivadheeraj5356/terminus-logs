# Wavelength calibration with intentional unit/index/revision defects
function build_wavelengths(    p, px, t_c, rev) {
  delete wavelength
  rev = effective_cal_rev(frame_cal_rev)
  if (!cal_lookup_latest(frame_instrument, rev)) return "missing_calibration"
  t_c = frame_temp_centi / 100.0
  for (p = 0; p < frame_sample_count; p++) {
    # BUG: one-based pixel index
    px = p + 1
  wavelength[p + 1] = cal_sel_c0 + cal_sel_c1 * px + cal_sel_c2 * px * px \
      + cal_sel_tc * (t_c - cal_sel_tref)
  }
  return ""
}

function cal_lookup_latest(instrument, _ignored,    k, best) {
  best = -1
  for (k in cal_c0) {
    split(k, parts, SUBSEP)
    if (parts[1] != instrument) continue
    if (parts[2] + 0 > best) {
      best = parts[2] + 0
      cal_sel_c0 = cal_c0[k]
      cal_sel_c1 = cal_c1[k]
      cal_sel_c2 = cal_c2[k]
      cal_sel_tc = cal_tc[k]
      cal_sel_tref = cal_tref[k]
    }
  }
  return best >= 0
}

function wavelength_at_pixel(p) {
  return wavelength[p + 1]
}
