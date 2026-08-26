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
  # BUG: off-by-one on negative conversion
  if (v >= 32768) return v - 65535
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
