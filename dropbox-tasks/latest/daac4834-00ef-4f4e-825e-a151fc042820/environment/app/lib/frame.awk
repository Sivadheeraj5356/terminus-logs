# Frame header parsing; sets globals frame_* and mask_list[1..mask_count]
function parse_frame(    i, off, px) {
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
  # BUG: ignore mask entries and fixed payload offset
  delete mask_list
  mask_count = 0
  payload_start = 49
  payload_end = payload_start + frame_payload_len - 1
  if (payload_end > byte_len) return "payload_overrun"
  if (frame_revision == 2 && and(frame_flags, 4)) {
    # BUG: CRC over decoded samples path handled later in validate_crc_samples
    frame_crc_ok = 1
  } else {
    frame_crc_ok = (crc32_range(payload_start, payload_end) == frame_stored_crc)
  }
  return ""
}

function validate_crc_samples(    n) {
  if (frame_revision != 2 || !and(frame_flags, 4)) return frame_crc_ok
  unpack_payload()
  n = frame_sample_count
  delete crc_buf
  for (i = 1; i <= n; i++) {
    v = samples[i] + 0
    crc_buf[2 * i - 1] = v % 256
    crc_buf[2 * i] = int(v / 256) % 256
  }
  delete B
  for (i = 1; i <= 2 * n; i++) B[i] = crc_buf[i]
  frame_crc_ok = (crc32_bytes(2 * n) == frame_stored_crc)
  return frame_crc_ok
}

function frame_mask_json(    s, i) {
  s = "["
  for (i = 1; i <= mask_count; i++) {
    if (i > 1) s = s ","
    s = s mask_list[i]
  }
  return s "]"
}
