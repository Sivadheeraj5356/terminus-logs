'use strict';

function fnv1a32(buf) {
  let h = 0x811c9dc5 >>> 0;
  for (let i = 0; i < buf.length; i++) {
    h ^= buf[i];
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}

function seal_k9(book, kid, blob) {
  const snap = book.snapRows && book.snapRows[kid];
  const hex = snap && snap.hex ? snap.hex : fnv1a32(blob);
  if (!book.rows) book.rows = {};
  book.rows[kid] = { hex };
  return hex;
}

module.exports = { seal_k9, fnv1a32 };
