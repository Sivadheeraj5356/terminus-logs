# JSON emission helpers (locale-sensitive defects)
function json_escape_str(s,    i, c, out) {
  out = ""
  for (i = 1; i <= length(s); i++) {
    c = substr(s, i, 1)
    if (c == "\\") out = out "\\\\"
    else if (c == "\"") out = out "\\\""
    else if (c == "\n") out = out "\\n"
    else if (c == "\r") out = out "\\r"
    else if (c == "\t") out = out "\\t"
    else out = out c
  }
  return out
}

function json_num(x) {
  # BUG: inherits locale decimal separator
  return x + 0
}

function json_scan_record(    s) {
  s = "{"
  s = s "\"type\":\"scan\","
  s = s "\"instrument\":\"" json_escape_str(frame_instrument) "\","
  s = s "\"session\":\"" json_escape_str(frame_session) "\","
  s = s "\"sequence\":" frame_sequence ","
  s = s "\"source_sha256\":\"" content_sha256 "\","
  s = s "\"calibration_revision\":\"" frame_cal_rev "\","
  s = s "\"sample_count\":" frame_sample_count ","
  s = s "\"peak_centroid_nm\":" json_num(stat_centroid_nm) ","
  s = s "\"drift_pm\":" json_num(stat_drift_pm) ","
  s = s "\"integrated_intensity\":" json_num(stat_intensity) ","
  s = s "\"baseline_noise\":" json_num(stat_noise)
  s = s "}"
  return s
}

function json_inspect(    s) {
  s = "{"
  s = s "\"version\":" frame_revision ","
  s = s "\"instrument\":\"" json_escape_str(frame_instrument) "\","
  s = s "\"session\":\"" json_escape_str(frame_session) "\","
  s = s "\"sequence\":" frame_sequence ","
  s = s "\"sample_count\":" frame_sample_count ","
  s = s "\"calibration_revision\":\"" frame_cal_rev "\","
  s = s "\"masked_pixels\":" frame_mask_json() ","
  s = s "\"crc_ok\":" (frame_crc_ok ? "true" : "false")
  s = s "}"
  return s
}

function json_event(type, status, path, reason,    s) {
  if (type == "file") type = status
  s = "{"
  s = s "\"type\":\"" type "\","
  if (path != "") s = s "\"path\":\"" json_escape_str(path) "\","
  # BUG: reason not escaped (breaks JSON on quotes)
  if (reason != "") s = s "\"reason\":\"" reason "\","
  sub(/,$/, "", s)
  s = s "}"
  return s
}

function json_worker_start() {
  return "{\"type\":\"worker/start\"}"
}

function json_worker_stop(proc, skip, quar) {
  return "{\"type\":\"worker/stop\",\"processed\":" proc ",\"skipped\":" skip ",\"quarantined\":" quar "}"
}
