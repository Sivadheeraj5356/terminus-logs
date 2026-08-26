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
