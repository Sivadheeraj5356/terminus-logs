'use strict';

function pin_m3(state, tag) {
  const hits = state && state.pins ? state.pins[tag] || 0 : 0;
  return { hits, ok: hits >= 0 };
}

module.exports = { pin_m3 };
