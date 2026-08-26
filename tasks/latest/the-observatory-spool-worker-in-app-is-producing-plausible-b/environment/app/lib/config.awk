# Operational configuration; precedence env > site > defaults for paths and analysis windows
function load_config(defaults_path, site_path,    line, k, v) {
  cfg_inbox = "/data/inbox"
  cfg_work = "/data/work"
  cfg_archive = "/data/archive"
  cfg_quarantine = "/data/quarantine"
  cfg_state = "/data/state"
  cfg_output = "/output/drift.jsonl"
  cfg_def = "/app/container/specz-worker.def"
  cfg_reference_nm = meta_reference_nm
  cfg_peak_lo = meta_peak_lo
  cfg_peak_hi = meta_peak_hi
  cfg_baseline1_lo = meta_baseline1_lo
  cfg_baseline1_hi = meta_baseline1_hi
  cfg_baseline2_lo = meta_baseline2_lo
  cfg_baseline2_hi = meta_baseline2_hi
  cfg_force_cal_rev = 0

  # BUG: site applied before defaults, then defaults overwrite site
  parse_conf(site_path)
  parse_conf(defaults_path)

  if (ENVIRON["SPECZ_INBOX"] != "") cfg_inbox = ENVIRON["SPECZ_INBOX"]
  if (ENVIRON["SPECZ_WORK"] != "") cfg_work = ENVIRON["SPECZ_WORK"]
  if (ENVIRON["SPECZ_ARCHIVE"] != "") cfg_archive = ENVIRON["SPECZ_ARCHIVE"]
  if (ENVIRON["SPECZ_QUARANTINE"] != "") cfg_quarantine = ENVIRON["SPECZ_QUARANTINE"]
  if (ENVIRON["SPECZ_STATE"] != "") cfg_state = ENVIRON["SPECZ_STATE"]
  if (ENVIRON["SPECZ_OUTPUT"] != "") cfg_output = ENVIRON["SPECZ_OUTPUT"]
  if (ENVIRON["SPECZ_DEF"] != "") cfg_def = ENVIRON["SPECZ_DEF"]
  if (ENVIRON["SPECZ_REFERENCE_NM"] != "") cfg_reference_nm = ENVIRON["SPECZ_REFERENCE_NM"] + 0
  if (ENVIRON["SPECZ_PEAK_WINDOW"] != "") {
    split(ENVIRON["SPECZ_PEAK_WINDOW"], w, /,/)
    cfg_peak_lo = w[1] + 0
    cfg_peak_hi = w[2] + 0
  }
}

function parse_conf(path,    line, k, v) {
  while ((getline line < path) > 0) {
    sub(/#.*/, "", line)
    if (line ~ /^[ \t]*$/) continue
    split(line, kv, /=[ \t]*/)
    k = kv[1]
    gsub(/^[ \t]+|[ \t]+$/, "", k)
    v = kv[2]
    gsub(/^[ \t]+|[ \t]+$/, "", v)
    # BUG: empty site value becomes explicit zero
    if (v == "") v = "0"
    apply_conf(k, v)
  }
  close(path)
}

function apply_conf(k, v) {
  if (k == "inbox") cfg_inbox = v
  else if (k == "work") cfg_work = v
  else if (k == "archive") cfg_archive = v
  else if (k == "quarantine") cfg_quarantine = v
  else if (k == "state") cfg_state = v
  else if (k == "output") cfg_output = v
  else if (k == "definition") cfg_def = v
  else if (k == "reference_nm") cfg_reference_nm = v + 0
  else if (k == "peak_window_nm") {
    split(v, w, /,/)
    cfg_peak_lo = w[1] + 0
    cfg_peak_hi = w[2] + 0
  } else if (k == "baseline_windows_px") {
    split(v, w, /,/)
    split(w[1], a, /:/)
    split(w[2], b, /:/)
    cfg_baseline1_lo = a[1] + 0
    cfg_baseline1_hi = a[2] + 0
    cfg_baseline2_lo = b[1] + 0
    cfg_baseline2_hi = b[2] + 0
  } else if (k == "calibration_revision") {
    # BUG: site may override frame revision selection
    cfg_force_cal_rev = v + 0
  }
}

function effective_cal_rev(frame_rev) {
  if (cfg_force_cal_rev > 0) return cfg_force_cal_rev
  return frame_rev
}
