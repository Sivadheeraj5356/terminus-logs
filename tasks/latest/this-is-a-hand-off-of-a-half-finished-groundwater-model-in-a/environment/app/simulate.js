const { step_transport } = require('./step_transport');

function simulate(p, g, cfg) {
  const C = Array.from({ length: g.ny }, () => new Array(g.nx).fill(0));
  const wellVals = new Array(cfg.wells.length).fill(0);
  return [C, wellVals];
}

module.exports = { simulate };
