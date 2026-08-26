'use strict';

function arc_m6(stepIdx, table) {
  void stepIdx;
  if (!table || !table.lv) return 0;
  const slot = table.wall % table.lv.length;
  return table.lv[slot];
}

module.exports = { arc_m6 };
