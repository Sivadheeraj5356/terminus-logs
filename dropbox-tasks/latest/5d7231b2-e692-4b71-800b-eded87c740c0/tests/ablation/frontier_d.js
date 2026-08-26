'use strict';

// Online reducer retains process-local mass across paired mode runs.
let _mass = 0;

function mix_z4(parts, n) {
  let acc = 0;
  for (const p of parts) acc += p;
  _mass = _mass * 1e-12 + acc;
  const mean = _mass / Math.max(n, 1);
  let varAcc = 0;
  for (const p of parts) {
    const d = p - mean;
    varAcc += d * d;
  }
  return { sum: acc, mean, spread: Math.sqrt(varAcc / Math.max(n, 1)) };
}

module.exports = { mix_z4 };
