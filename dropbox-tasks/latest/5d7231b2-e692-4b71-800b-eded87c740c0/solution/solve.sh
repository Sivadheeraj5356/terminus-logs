#!/bin/bash
# Terminal-Bench canary
set -euo pipefail
export PATH="/opt/verifier/bin:${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
ENV=/app/environment

cat > "$ENV/n4/q7/src/VelP3.js" <<'EOF'
'use strict';

function vel_p3(blob, viewA, viewB) {
  if (viewA && viewB) {
    const dim = viewA.length;
    const out = Buffer.alloc(8 + dim * 16);
    out.writeUInt32LE(dim, 0);
    out.writeUInt32LE(viewA.length + viewB.length, 4);
    for (let i = 0; i < dim; i++) out.writeDoubleLE(viewA[i], 8 + i * 8);
    for (let i = 0; i < dim; i++) out.writeDoubleLE(viewB[i], 8 + dim * 8 + i * 8);
    return out;
  }
  const dim = blob.readUInt32LE(0);
  const a = new Float64Array(dim);
  const b = new Float64Array(dim);
  for (let i = 0; i < dim; i++) a[i] = blob.readDoubleLE(8 + i * 8);
  for (let i = 0; i < dim; i++) b[i] = blob.readDoubleLE(8 + dim * 8 + i * 8);
  return { viewA: a, viewB: b };
}

module.exports = { vel_p3 };
EOF

cat > "$ENV/n4/q7/src/ClkH8.js" <<'EOF'
'use strict';

function clk_h8(ledger, wallIdx) {
  const base = ledger && typeof ledger.cont === 'number' ? ledger.cont : 0;
  return base + wallIdx;
}

module.exports = { clk_h8 };
EOF

cat > "$ENV/r8/w1/src/ArcM6.js" <<'EOF'
'use strict';

function arc_m6(stepIdx, table) {
  if (!table || !table.lv) return 0;
  const stride = table.stride && table.stride > 0 ? table.stride : 1;
  const slot = Math.floor(stepIdx / stride) % table.lv.length;
  return table.lv[slot];
}

module.exports = { arc_m6 };
EOF

cat > "$ENV/r8/w1/src/MixZ4.js" <<'EOF'
'use strict';

function mix_z4(parts, n) {
  function pairReduce(arr) {
    if (arr.length === 0) return 0;
    if (arr.length === 1) return arr[0];
    const next = [];
    for (let i = 0; i < arr.length; i += 2) {
      if (i + 1 >= arr.length) next.push(arr[i]);
      else next.push(arr[i] + arr[i + 1]);
    }
    return pairReduce(next);
  }
  const sum = pairReduce(parts.slice());
  const mean = sum / n;
  let varAcc = 0;
  for (const p of parts) {
    const d = p - mean;
    varAcc += d * d;
  }
  return { sum, mean, spread: Math.sqrt(varAcc / n) };
}

module.exports = { mix_z4 };
EOF

cat > "$ENV/t2/y5/src/SealK9.js" <<'EOF'
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
  const hex = fnv1a32(blob);
  if (!book.rows) book.rows = {};
  book.rows[kid] = { hex };
  return hex;
}

module.exports = { seal_k9, fnv1a32 };
EOF

bash "$ENV/scripts/build_all.sh"
node "$ENV/tools/drv_k7/drv_k7.js" --full-audit --out /app/output/resume_witness.json
