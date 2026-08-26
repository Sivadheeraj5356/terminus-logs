# Parse Apptainer definition labels into cal_* and meta_* globals
function load_apptainer_meta(def_path,    line, key, val, inst, rev) {
  delete cal_c0; delete cal_c1; delete cal_c2; delete cal_tc; delete cal_tref
  meta_reference_nm = 656.281230
  meta_peak_lo = 655.70
  meta_peak_hi = 656.90
  meta_baseline1_lo = 0
  meta_baseline1_hi = 31
  meta_baseline2_lo = 224
  meta_baseline2_hi = 255
  while ((getline line < def_path) > 0) {
    if (match(line, /^[ \t]*org\.obs\.specz\.reference\.([A-Z0-9]+)[ \t]*=[ \t]*"([^"]+)"/, m)) {
      meta_reference_nm = m[2] + 0
    } else if (match(line, /^[ \t]*org\.obs\.specz\.peak_window_nm[ \t]*=[ \t]*"([^"]+)"/, m)) {
      split(m[1], w, /,/)
      meta_peak_lo = w[1] + 0
      meta_peak_hi = w[2] + 0
    } else if (match(line, /^[ \t]*org\.obs\.specz\.baseline_windows_px[ \t]*=[ \t]*"([^"]+)"/, m)) {
      split(m[1], w, /,/)
      split(w[1], a, /:/)
      split(w[2], b, /:/)
      meta_baseline1_lo = a[1] + 0
      meta_baseline1_hi = a[2] + 0
      meta_baseline2_lo = b[1] + 0
      meta_baseline2_hi = b[2] + 0
    } else if (match(line, /^[ \t]*org\.obs\.specz\.calibration\.([A-Z0-9]+)\.([0-9]+)[ \t]*=[ \t]*"([^"]+)"/, m)) {
      inst = m[1]
      rev = m[2] + 0
      split(m[3], t, /,/)
      cal_key = inst SUBSEP rev
      cal_c0[cal_key] = t[1] + 0
      cal_c1[cal_key] = t[2] + 0
      cal_c2[cal_key] = t[3] + 0
      cal_tc[cal_key] = t[4] + 0
      cal_tref[cal_key] = t[5] + 0
    }
  }
  close(def_path)
}

function cal_lookup(instrument, rev,    k) {
  k = instrument SUBSEP rev
  if (!(k in cal_c0)) return 0
  cal_sel_c0 = cal_c0[k]
  cal_sel_c1 = cal_c1[k]
  cal_sel_c2 = cal_c2[k]
  cal_sel_tc = cal_tc[k]
  cal_sel_tref = cal_tref[k]
  return 1
}
