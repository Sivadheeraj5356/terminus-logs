# Decode payload into samples[1..frame_sample_count]
function unpack_payload(    err) {
  delete samples
  if (and(frame_flags, 1)) {
    # BUG: reverse before decode
    reverse_payload_bytes()
  }
  if (and(frame_flags, 4)) {
    err = unpack_delta8()
  } else {
    err = unpack_raw12()
  }
  return err
}

function reverse_payload_bytes(    i, t) {
  for (i = payload_start; i <= payload_end; i++) {
    j = payload_start + payload_end - i
    if (i >= j) break
    t = B[i]; B[i] = B[j]; B[j] = t
  }
}

function unpack_raw12(    i, off, b0, b1, b2, s0, s1, idx) {
  delete samples
  off = payload_start
  idx = 0
  while (idx < frame_sample_count) {
    if (off + 2 > payload_end) break
    b0 = u8(off); off++
    b1 = u8(off); off++
    b2 = u8(off); off++
    # BUG: big-endian style grouping
    s0 = (b0 * 16) + int(b1 / 16)
    s1 = ((b1 % 16) * 256) + b2
    samples[++idx] = s0
    if (idx < frame_sample_count) samples[++idx] = s1
  }
  # BUG: odd tail may consume extra high nibble from next group
  return (idx == frame_sample_count) ? "" : "sample_count_mismatch"
}

function unpack_delta8(    i, off, b, delta, val, first) {
  delete samples
  off = payload_start
  first = u16le(off)
  samples[1] = first % 4096
  off += 2
  i = 2
  while (i <= frame_sample_count) {
    if (off > payload_end) break
    b = u8(off); off++
    # BUG: signed conversion before escape check
    delta = (b < 128) ? b : b - 256
    if (b == 0x80) {
      val = u16le(off) % 4096
      off += 2
      samples[i++] = val
    } else {
      val = samples[i - 1] + delta
      samples[i++] = val % 4096
    }
  }
  return ""
}

function reverse_samples(    i, n, t) {
  n = frame_sample_count
  for (i = 1; i <= int(n / 2); i++) {
    t = samples[i]
    samples[i] = samples[n - i + 1]
    samples[n - i + 1] = t
  }
}
