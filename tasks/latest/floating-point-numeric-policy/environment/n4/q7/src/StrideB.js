'use strict';

function stride_b(n, span) {
  const s = Math.max(1, Math.floor(span / Math.max(1, n)));
  return { s, span };
}

module.exports = { stride_b };
