'use strict';

function vel_p3(blob, viewA, viewB) {
  if (viewA && viewB) {
    const dim = viewA.length;
    const out = Buffer.alloc(8 + dim * 8);
    out.writeUInt32LE(dim, 0);
    out.writeUInt32LE(viewA.length + viewB.length, 4);
    for (let i = 0; i < dim; i++) out.writeFloatLE(viewA[i], 8 + i * 4);
    for (let i = 0; i < dim; i++) out.writeFloatLE(viewB[i], 8 + dim * 4 + i * 4);
    return out;
  }
  const dim = blob.readUInt32LE(0);
  const a = new Float64Array(dim);
  const b = new Float64Array(dim);
  for (let i = 0; i < dim; i++) a[i] = blob.readFloatLE(8 + i * 4);
  for (let i = 0; i < dim; i++) b[i] = 0;
  return { viewA: a, viewB: b };
}

module.exports = { vel_p3 };
