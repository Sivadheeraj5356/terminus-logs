#!/usr/bin/env bash
set -euo pipefail
cd /app

cat >scripts/specz-worker <<'BASH'
#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${SPECZ_APP:-/app}"
LIB="${APP_ROOT}/lib"
DEF="${APP_ROOT}/container/specz-worker.def"
DEFAULTS="${APP_ROOT}/config/defaults.conf"
SITE="${SPECZ_CONFIG:-${APP_ROOT}/config/site.conf}"

export LC_NUMERIC=C
export LC_ALL=C

AWK_LIBS=(
  -f "${LIB}/bytes.awk"
  -f "${LIB}/crc32.awk"
  -f "${LIB}/frame.awk"
  -f "${LIB}/unpack.awk"
  -f "${LIB}/apptainer_meta.awk"
  -f "${LIB}/config.awk"
  -f "${LIB}/calibrate.awk"
  -f "${LIB}/statistics.awk"
  -f "${LIB}/state.awk"
  -f "${LIB}/json.awk"
)

usage() {
  echo "usage: specz-worker --once | inspect <frame>" >&2
  exit 2
}

run_inspect() {
  local frame="$1"
  gawk "${AWK_LIBS[@]}" -v frame_path="${frame}" -e '
    BEGIN {
      load_apptainer_meta("'"${DEF}"'")
      load_config("'"${DEFAULTS}"'", "'"${SITE}"'")
      if (load_bytes_from_file(frame_path) < 48) { print "{\"error\":\"truncated\"}"; exit 1 }
      err = parse_frame()
      if (err != "") { print "{\"error\":\"" err "\"}"; exit 1 }
      print json_inspect()
    }
  '
}

collect_spool_files() {
  local inbox work f
  inbox="${SPECZ_INBOX:-/data/inbox}"
  work="${SPECZ_WORK:-/data/work}"
  mapfile -t SPOOL_FILES < <(
    {
      shopt -s nullglob
      for f in "${inbox}"/*.spz; do [[ -f "$f" ]] && printf '%s\n' "$f"; done
      for f in "${work}"/*.processing; do [[ -f "$f" ]] && printf '%s\n' "$f"; done
    } | LC_ALL=C sort
  )
}

run_once() {
  local -a files=()
  collect_spool_files
  files=("${SPOOL_FILES[@]:-}")

  run_once_awk() {
    gawk "${AWK_LIBS[@]}" -e '
    BEGIN {
      processed = skipped = quarantined = 0
      load_apptainer_meta("'"${DEF}"'")
      load_config("'"${DEFAULTS}"'", "'"${SITE}"'")
      load_manifest()
      print json_worker_start()
      fflush()
      for (ai = 1; ai < ARGC; ai++) {
        if (ARGV[ai] == "") continue
        process_file(ARGV[ai])
        ARGV[ai] = ""
      }
    }
    function basename(p,    a) { split(p, a, "/"); return a[length(a)] }
    function claim_path(src,    base, dst) {
      base = basename(src)
      sub(/\.processing$/, "", base)
      dst = cfg_work "/" base ".processing"
      if (index(src, ".processing") > 0) return src
      system("mkdir -p \"" cfg_work "\"")
      system("mv \"" src "\" \"" dst "\"")
      return dst
    }
    function archive_path(src,    base, dst) {
      base = basename(src)
      sub(/\.processing$/, "", base)
      dst = cfg_archive "/" base
      system("mkdir -p \"" cfg_archive "\"")
      system("mv \"" src "\" \"" dst "\"")
    }
    function quarantine_path(src, reason,    base, dst, rj) {
      base = basename(src)
      sub(/\.processing$/, "", base)
      dst = cfg_quarantine "/" base
      system("mkdir -p \"" cfg_quarantine "\"")
      system("mv \"" src "\" \"" dst "\"")
      rj = cfg_quarantine "/" base ".reason.json"
      print json_event("file", "quarantined", dst, reason) > rj
      close(rj)
      quarantined++
      print json_event("file", "quarantined", dst, reason)
      fflush()
    }
    function process_file(src,    path, hash, err, rec) {
      path = claim_path(src)
      hash = sha256_file(path)
      content_sha256 = hash
      if (should_skip_replay(hash)) {
        archive_path(path)
        skipped++
        print json_event("file", "skipped", path, "content_replay")
        fflush()
        return
      }
      if (load_bytes_from_file(path) < 48) { quarantine_path(path, "truncated_header"); return }
      err = parse_frame()
      if (err != "") { quarantine_path(path, err); return }
      if (!frame_crc_ok) { quarantine_path(path, "crc_mismatch"); return }
      err = unpack_payload()
      if (err != "") { quarantine_path(path, err); return }
      if (should_quarantine_conflict(frame_instrument, frame_session, frame_sequence, hash)) {
        quarantine_path(path, "logical_hash_conflict")
        return
      }
      if (is_committed(hash)) {
        archive_path(path)
        skipped++
        print json_event("file", "skipped", path, "already_committed")
        fflush()
        return
      }
      err = compute_statistics()
      if (err != "") { quarantine_path(path, err); return }
      rec = json_scan_record()
      commit_scan(rec, frame_instrument, frame_session, frame_sequence, hash)
      archive_path(path)
      processed++
      print json_event("file", "processed", path, "")
      fflush()
    }
    END {
      materialize_output()
      print json_worker_stop(processed, skipped, quarantined)
      fflush()
    }
  ' "$@"
  }

  if ((${#files[@]} == 0)); then
    run_once_awk < /dev/null
  else
    run_once_awk "${files[@]}"
  fi
}

main() {
  [[ $# -ge 1 ]] || usage
  case "$1" in
    --once) run_once ;;
    inspect)
      [[ $# -eq 2 ]] || usage
      run_inspect "$2"
      ;;
    *) usage ;;
  esac
}

main "$@"
BASH

cat >lib/bytes.awk <<'AWK'
# Byte array helpers over global B[1..byte_len]
function load_bytes_from_file(path,    cmd, line, n, i, a) {
  n = 0
  cmd = "od -An -v -t u1 \"" path "\""
  while ((cmd | getline line) > 0) {
    split(line, a, /[ \t]+/)
    for (i = 1; i <= length(a); i++) {
      if (a[i] == "") continue
      n++
      B[n] = a[i] + 0
    }
  }
  close(cmd)
  byte_len = n
  return n
}

function u8(i) { return B[i] + 0 }

function u16le(i) {
  return (B[i] + 0) + 256 * (B[i + 1] + 0)
}

function u32le(i) {
  return (B[i] + 0) + 256 * (B[i + 1] + 0) + 65536 * (B[i + 2] + 0) + 16777216 * (B[i + 3] + 0)
}

function i16le(i,    v) {
  v = u16le(i)
  if (v >= 32768) return v - 65536
  return v
}

function ascii_field(start, len,    s, i, c) {
  s = ""
  for (i = 0; i < len; i++) {
    c = u8(start + i)
    if (c == 0) break
    s = s sprintf("%c", c)
  }
  return s
}
AWK

cat >lib/frame.awk <<'AWK'
# Frame header parsing; sets globals frame_* and mask_list[1..mask_count]
function parse_frame(    i, off, px, seen) {
  if (byte_len < 48) return "truncated_header"
  if (ascii_field(1, 4) != "SPZ0") return "bad_magic"
  frame_revision = u8(5)
  if (frame_revision != 1 && frame_revision != 2) return "bad_revision"
  frame_flags = u8(6)
  if (and(frame_flags, 248)) return "reserved_flags"
  frame_header_len = u16le(7)
  frame_instrument = ascii_field(9, 8)
  frame_session = ascii_field(17, 8)
  frame_sequence = u32le(25)
  frame_acq = u32le(29)
  frame_sample_count = u16le(33)
  frame_integration = u16le(35)
  frame_temp_centi = i16le(37)
  frame_cal_rev = u8(39)
  mask_count = u8(40)
  frame_payload_len = u32le(41)
  frame_stored_crc = u32le(45)
  if (frame_header_len != 48 + 2 * mask_count) return "header_len_mismatch"
  if (frame_sample_count < 1 || frame_sample_count > 4096) return "bad_sample_count"
  if (byte_len < frame_header_len + frame_payload_len) return "payload_overrun"
  delete mask_list
  off = 49
  for (i = 1; i <= mask_count; i++) {
    if (off + 1 > byte_len) return "truncated_mask"
    px = u16le(off)
    off += 2
    if (px >= frame_sample_count) return "bad_mask_index"
    if (seen[px]) return "duplicate_mask"
    seen[px] = 1
    mask_list[i] = px
  }
  payload_start = frame_header_len + 1
  payload_end = payload_start + frame_payload_len - 1
  if (payload_end > byte_len) return "payload_overrun"
  frame_crc_ok = (crc32_range(payload_start, payload_end) == frame_stored_crc)
  return ""
}

function frame_mask_json(    s, i) {
  s = "["
  for (i = 1; i <= mask_count; i++) {
    if (i > 1) s = s ","
    s = s mask_list[i]
  }
  return s "]"
}
AWK

cat >lib/unpack.awk <<'AWK'
# Decode payload into samples[1..frame_sample_count]
function unpack_payload(    i, off, b0, b1, b2, s0, s1, b, delta, val, n) {
  delete samples
  n = frame_sample_count
  if (and(frame_flags, 4)) {
    unpack_delta8()
  } else {
    unpack_raw12()
  }
  if (and(frame_flags, 1)) {
    reverse_samples()
  }
  if (length(samples) != n) return "sample_count_mismatch"
  return ""
}

function unpack_raw12(    i, off, b0, b1, b2, s0, s1, idx) {
  delete samples
  off = payload_start
  idx = 0
  while (idx < frame_sample_count) {
    b0 = u8(off); off++
    if (idx + 1 < frame_sample_count) {
      b1 = u8(off); off++
      b2 = u8(off); off++
      s0 = b0 + ((b1 % 16) * 256)
      s1 = int(b1 / 16) + (b2 * 16)
      samples[++idx] = s0
      samples[++idx] = s1
    } else {
      b1 = u8(off); off++
      if (int(b1 / 16) != 0) samples[++idx] = -1
      else samples[++idx] = b0 + ((b1 % 16) * 256)
    }
  }
}

function unpack_delta8(    i, off, b, delta, val, first) {
  delete samples
  off = payload_start
  first = u16le(off)
  if (int(first / 4096) != 0) { samples[1] = -1; return }
  samples[1] = first % 4096
  off += 2
  i = 2
  while (i <= frame_sample_count) {
    if (off > payload_end) break
    b = u8(off); off++
    if (b == 0x80) {
      val = u16le(off) % 4096
      off += 2
      samples[i++] = val
    } else {
      delta = (b < 128) ? b : b - 256
      val = samples[i - 1] + delta
      if (val < 0 || val > 4095) { samples[i] = -1; return }
      samples[i++] = val
    }
  }
}

function reverse_samples(    i, n, t) {
  n = frame_sample_count
  for (i = 1; i <= int(n / 2); i++) {
    t = samples[i]
    samples[i] = samples[n - i + 1]
    samples[n - i + 1] = t
  }
}
AWK

cat >lib/apptainer_meta.awk <<'AWK'
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
AWK

cat >lib/config.awk <<'AWK'
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

  parse_conf(defaults_path)
  parse_conf(site_path)

  if (ENVIRON["SPECZ_INBOX"] != "") cfg_inbox = ENVIRON["SPECZ_INBOX"]
  if (ENVIRON["SPECZ_WORK"] != "") cfg_work = ENVIRON["SPECZ_WORK"]
  if (ENVIRON["SPECZ_ARCHIVE"] != "") cfg_archive = ENVIRON["SPECZ_ARCHIVE"]
  if (ENVIRON["SPECZ_QUARANTINE"] != "") cfg_quarantine = ENVIRON["SPECZ_QUARANTINE"]
  if (ENVIRON["SPECZ_STATE"] != "") cfg_state = ENVIRON["SPECZ_STATE"]
  if (ENVIRON["SPECZ_OUTPUT"] != "") cfg_output = ENVIRON["SPECZ_OUTPUT"]
  if (ENVIRON["SPECZ_DEF"] != "") cfg_def = ENVIRON["SPECZ_DEF"]
  # Analysis reference/windows follow site.conf over environment (see operator runbook).
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
    if (v == "") continue
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
  }
  # frame calibration_revision is never overridden from site config
}
AWK

cat >lib/calibrate.awk <<'AWK'
# Wavelength calibration: lambda_nm(p,T) = c0 + c1*p + c2*p^2 + (tc*(T-tref))/1000
function build_wavelengths(    p, px, t_c) {
  delete wavelength
  if (!cal_lookup(frame_instrument, frame_cal_rev)) return "missing_calibration"
  t_c = frame_temp_centi / 100.0
  for (p = 0; p < frame_sample_count; p++) {
    px = p
    wavelength[p + 1] = cal_sel_c0 + cal_sel_c1 * px + cal_sel_c2 * px * px \
      + (cal_sel_tc * (t_c - cal_sel_tref)) / 1000.0
  }
  return ""
}

function wavelength_at_pixel(p) {
  return wavelength[p + 1]
}
AWK

cat >lib/statistics.awk <<'AWK'
# Spectral statistics per current operating policy
function compute_statistics(    err, p, lam, a, b, n, sx, sy, sxx, sxy, denom) {
  err = build_wavelengths()
  if (err != "") return err
  build_mask_set()
  fit_baseline_ols(a, b)
  collect_residuals(a, b)
  compute_peak_metrics()
  compute_baseline_noise()
  stat_drift_pm = (stat_centroid_nm - cfg_reference_nm) * 1000.0
  return ""
}

function build_mask_set(    i) {
  delete mask_set
  for (i = 1; i <= mask_count; i++) mask_set[mask_list[i]] = 1
}

function fit_baseline_ols(a, b,    p, lam, n, sx, sy, sxx, sxy, denom) {
  n = sx = sy = sxx = sxy = 0
  for (p = 0; p < frame_sample_count; p++) {
    if (mask_set[p]) continue
    if (!pixel_in_baseline_windows(p)) continue
    lam = wavelength[p + 1]
    val = samples[p + 1] + 0
    n++
    sx += lam
    sy += val
    sxx += lam * lam
    sxy += lam * val
  }
  if (n < 2) { a = 0; b = 0; return }
  denom = n * sxx - sx * sx
  if (denom == 0) { a = sy / n; b = 0; return }
  b = (n * sxy - sx * sy) / denom
  a = (sy - b * sx) / n
  baseline_a = a
  baseline_b = b
}

function pixel_in_baseline_windows(p,    lo1, hi1, lo2, hi2) {
  lo1 = cfg_baseline1_lo; hi1 = cfg_baseline1_hi
  lo2 = cfg_baseline2_lo; hi2 = cfg_baseline2_hi
  return (p >= lo1 && p <= hi1) || (p >= lo2 && p <= hi2)
}

function collect_residuals(a, b,    p, lam, res) {
  delete residual_lam
  delete residual_val
  res_count = 0
  baseline_side_n = 0
  delete baseline_side_res
  for (p = 0; p < frame_sample_count; p++) {
    if (mask_set[p]) continue
    lam = wavelength[p + 1]
    res = (samples[p + 1] + 0) - (baseline_a + baseline_b * lam)
    res_count++
    residual_lam[res_count] = lam
    residual_val[res_count] = res
    if (pixel_in_baseline_windows(p)) {
      baseline_side_n++
      baseline_side_res[baseline_side_n] = res
    }
  }
}

function compute_peak_metrics(    i, lam, res, w, sumw, sumwl, pts, intensity) {
  sumw = sumwl = 0
  stat_intensity = 0
  peak_pts = 0
  delete peak_x
  delete peak_y
  for (i = 1; i <= res_count; i++) {
    lam = residual_lam[i]
    res = residual_val[i]
    if (lam < cfg_peak_lo || lam > cfg_peak_hi) continue
    w = (res > 0) ? res : 0
    if (w > 0) {
      sumw += w
      sumwl += lam * w
    }
    peak_pts++
    peak_x[peak_pts] = lam
    peak_y[peak_pts] = (res > 0) ? res : 0
  }
  if (sumw > 0) stat_centroid_nm = sumwl / sumw
  else stat_centroid_nm = cfg_reference_nm
  # trapezoidal integration in wavelength space
  sort_peak_points()
  for (i = 2; i <= peak_pts; i++) {
    stat_intensity += (peak_y[i - 1] + peak_y[i]) * 0.5 * (peak_x[i] - peak_x[i - 1])
  }
}

function sort_peak_points(    i, j, tx, ty) {
  for (i = 1; i <= peak_pts; i++) {
    for (j = i + 1; j <= peak_pts; j++) {
      if (peak_x[j] < peak_x[i]) {
        tx = peak_x[i]; peak_x[i] = peak_x[j]; peak_x[j] = tx
        ty = peak_y[i]; peak_y[i] = peak_y[j]; peak_y[j] = ty
      }
    }
  }
}

function compute_baseline_noise(    i, mean, var) {
  if (baseline_side_n > 1) {
    mean = 0
    for (i = 1; i <= baseline_side_n; i++) mean += baseline_side_res[i]
    mean /= baseline_side_n
    var = 0
    for (i = 1; i <= baseline_side_n; i++) var += (baseline_side_res[i] - mean) ^ 2
    stat_noise = sqrt(var / (baseline_side_n - 1))
  } else {
    stat_noise = 0
  }
}
AWK

cat >lib/state.awk <<'AWK'
# Checkpoint state: manifest, fragments, output materialization
function sha256_file(path,    cmd, h) {
  cmd = "sha256sum \"" path "\" 2>/dev/null"
  cmd | getline h
  close(cmd)
  split(h, a, /[ \t]+/)
  return tolower(a[1])
}

function manifest_path() { return cfg_state "/manifest.tsv" }
function results_dir() { return cfg_state "/results" }
function fragment_path(hash) { return results_dir() "/" hash ".json" }

function load_manifest(    line, n, f) {
  delete man_hash
  delete man_inst
  delete man_sess
  delete man_seq
  delete man_frag
  delete content_seen
  man_count = 0
  f = manifest_path()
  if ((getline line < f) < 0) { close(f); return }
  do {
    if (line == "") continue
    n = split(line, a, /\t/)
    if (n < 5) continue
    man_count++
    man_hash[man_count] = a[1]
    man_inst[man_count] = a[2]
    man_sess[man_count] = a[3]
    man_seq[man_count] = a[4] + 0
    man_frag[man_count] = a[5]
    content_seen[a[1]] = 1
    logical_key = a[2] SUBSEP a[3] SUBSEP a[4]
    logical_hash[logical_key] = a[1]
  } while ((getline line < f) > 0)
  close(f)
}

function logical_key_of(inst, sess, seq) {
  return inst SUBSEP sess SUBSEP seq
}

function find_manifest_by_hash(h,    i) {
  for (i = 1; i <= man_count; i++) if (man_hash[i] == h) return i
  return 0
}

function find_manifest_by_logical(inst, sess, seq,    i, k) {
  k = logical_key_of(inst, sess, seq)
  if (!(k in logical_hash)) return 0
  return find_manifest_by_hash(logical_hash[k])
}

function should_skip_replay(hash) {
  return (hash in content_seen)
}

function should_quarantine_conflict(inst, sess, seq, hash,    k) {
  k = logical_key_of(inst, sess, seq)
  if (!(k in logical_hash)) return 0
  return (logical_hash[k] != hash)
}

function commit_scan(fragment_json, inst, sess, seq, hash,    frag, tmp, man, line) {
  system("mkdir -p \"" results_dir() "\"")
  frag = fragment_path(hash)
  tmp = frag ".tmp"
  print fragment_json > tmp
  close(tmp)
  system("mv \"" tmp "\" \"" frag "\"")
  man = manifest_path()
  tmp = man ".tmp"
  if (file_exists(man)) {
    while ((getline line < man) > 0) print line > tmp
    close(man)
  }
  print hash "\t" inst "\t" sess "\t" seq "\t" hash ".json" > tmp
  close(tmp)
  system("mv \"" tmp "\" \"" man "\"")
  man_count++
  man_hash[man_count] = hash
  man_inst[man_count] = inst
  man_sess[man_count] = sess
  man_seq[man_count] = seq + 0
  man_frag[man_count] = hash ".json"
  content_seen[hash] = 1
  logical_hash[logical_key_of(inst, sess, seq)] = hash
}

function file_exists(path,    r) {
  r = (system("test -f \"" path "\"") == 0)
  return r
}

function reconcile_orphans(    cmd, path, line, h, inst, sess, seq, frag) {
  cmd = "ls \"" results_dir() "\"/*.json 2>/dev/null"
  while ((cmd | getline path) > 0) {
    h = path
    sub(/.*\//, "", h)
    sub(/\.json$/, "", h)
    if (find_manifest_by_hash(h) > 0) continue
    frag = fragment_path(h)
    if ((getline line < frag) <= 0) { close(frag); continue }
    close(frag)
    if (!match(line, /"instrument":"([^"]+)"/, a)) continue
    inst = a[1]
    if (!match(line, /"session":"([^"]+)"/, a)) continue
    sess = a[1]
    if (!match(line, /"sequence":([0-9]+)/, a)) continue
    seq = a[1] + 0
    man_count++
    man_hash[man_count] = h
    man_inst[man_count] = inst
    man_sess[man_count] = sess
    man_seq[man_count] = seq
    man_frag[man_count] = h ".json"
    content_seen[h] = 1
    logical_hash[logical_key_of(inst, sess, seq)] = h
    append_manifest_line(h, inst, sess, seq)
  }
  close(cmd)
}

function append_manifest_line(h, inst, sess, seq,    man, tmp, line) {
  man = manifest_path()
  tmp = man ".tmp"
  if (file_exists(man)) {
    while ((getline line < man) > 0) print line > tmp
    close(man)
  }
  print h "\t" inst "\t" sess "\t" seq "\t" h ".json" > tmp
  close(tmp)
  system("mv \"" tmp "\" \"" man "\"")
}

function materialize_output(    tmp, i, frag, line) {
  reconcile_orphans()
  tmp = cfg_output ".tmp"
  system("mkdir -p /output")
  delete sort_inst; delete sort_sess; delete sort_seq; delete sort_frag
  sort_n = 0
  for (i = 1; i <= man_count; i++) {
    frag = results_dir() "/" man_frag[i]
    if (!file_exists(frag)) continue
    sort_n++
    sort_inst[sort_n] = man_inst[i]
    sort_sess[sort_n] = man_sess[i]
    sort_seq[sort_n] = man_seq[i]
    sort_frag[sort_n] = man_frag[i]
  }
  sort_entries()
  for (i = 1; i <= sort_n; i++) {
    frag = results_dir() "/" sort_frag[i]
    while ((getline line < frag) > 0) print line >> tmp
    close(frag)
  }
  close(tmp)
  if (sort_n > 0) system("mv \"" tmp "\" \"" cfg_output "\"")
  else system(": > \"" cfg_output "\"")
}

function sort_entries(    i, j, ti, ts, tq, th) {
  for (i = 1; i <= sort_n; i++) {
    for (j = i + 1; j <= sort_n; j++) {
      if (sort_inst[j] < sort_inst[i] || \
          (sort_inst[j] == sort_inst[i] && sort_sess[j] < sort_sess[i]) || \
          (sort_inst[j] == sort_inst[i] && sort_sess[j] == sort_sess[i] && sort_seq[j] < sort_seq[i])) {
        ti = sort_inst[i]; sort_inst[i] = sort_inst[j]; sort_inst[j] = ti
        ts = sort_sess[i]; sort_sess[i] = sort_sess[j]; sort_sess[j] = ts
        tq = sort_seq[i]; sort_seq[i] = sort_seq[j]; sort_seq[j] = tq
        th = sort_frag[i]; sort_frag[i] = sort_frag[j]; sort_frag[j] = th
      }
    }
  }
}

function is_committed(hash) {
  return (hash in content_seen) && file_exists(fragment_path(hash))
}
AWK

cat >lib/json.awk <<'AWK'
# JSON emission helpers (locale-independent)
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

function json_num(x,    s) {
  if (x != x) return "null"
  s = sprintf("%.9f", x + 0)
  sub(/\.?0+$/, "", s)
  if (s == "" || s == "-") s = "0"
  return s
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
  if (reason != "") s = s "\"reason\":\"" json_escape_str(reason) "\","
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
AWK

cat >lib/crc32.awk <<'AWK'
# CRC-32/ISO-HDLC over byte array B[1..n] slice [start..end]
function crc32_init(    i, j, c) {
  if (crc_ready) return
  for (i = 0; i < 256; i++) {
    c = i
    for (j = 0; j < 8; j++) {
      if (and(c, 1)) c = xor(rshift(c, 1), 0xEDB88320)
      else c = rshift(c, 1)
    }
    crc_table[i] = c
  }
  crc_ready = 1
}

function crc32_range(start, end,    crc, i, b, idx) {
  crc32_init()
  crc = 0xFFFFFFFF
  for (i = start; i <= end; i++) {
    b = B[i] + 0
    idx = and(xor(crc, b), 0xFF)
    crc = xor(rshift(crc, 8), crc_table[idx])
  }
  return xor(crc, 0xFFFFFFFF)
}

function crc32_bytes(n,    crc, i, b) {
  return crc32_range(1, n)
}
AWK

chmod +x /app/scripts/specz-worker
/app/tools/reset-visible-spool.sh
tmp_log="$(mktemp)"
timeout 120 /app/bin/specz-worker --once | tee "$tmp_log"
/app/tools/validate-jsonl.sh "$tmp_log"
/app/tools/validate-jsonl.sh /output/drift.jsonl
hash1="$(sha256sum /output/drift.jsonl | awk '{print $1}')"
timeout 30 /app/bin/specz-worker --once > /dev/null
hash2="$(sha256sum /output/drift.jsonl | awk '{print $1}')"
test "$hash1" = "$hash2"
timeout 30 /app/bin/specz-worker inspect /data/inbox/spc07-r11-even.spz | jq -e '.version and .instrument and .crc_ok != null' > /dev/null
rm -f "$tmp_log"
