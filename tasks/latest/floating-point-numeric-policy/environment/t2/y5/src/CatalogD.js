'use strict';

function catalog_d(ids) {
  return (ids || []).map((x) => String(x));
}

module.exports = { catalog_d };
