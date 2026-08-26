#!/bin/bash
set -euo pipefail

cat > "/app/environment/p3k/src/lane_a.mjs" <<'EOF'
import { triplesToView } from "../../common/view.mjs";

export function fn_p3(view, perm) {
  const n = view.dim;
  const inv = new Uint32Array(n);
  for (let i = 0; i < n; i++) inv[perm[i]] = i;
  const triples = [];
  for (let r = 0; r < n; r++) {
    for (let p = view.rp[r]; p < view.rp[r + 1]; p++) {
      const c = view.cols[p];
      let nr = inv[r];
      let nc = inv[c];
      const a = view.vals[p];
      if (view.half && nr > nc) {
        const t = nr;
        nr = nc;
        nc = t;
      }
      triples.push([nr, nc, a]);
    }
  }
  return triplesToView(triples, n, view.half, view);
}
EOF

cat > "/app/environment/w8n/src/lane_b.mjs" <<'EOF'
import { triplesToView } from "../../common/view.mjs";

export function fn_w8(halfView, dim) {
  const n = dim;
  if (!halfView.half) {
    return {
      dim: halfView.dim,
      half: false,
      vals: Float64Array.from(halfView.vals),
      cols: Uint32Array.from(halfView.cols),
      rp: Uint32Array.from(halfView.rp),
      abs_band: halfView.abs_band,
      rel_band: halfView.rel_band,
      x_seed: halfView.x_seed,
      pack_id: halfView.pack_id,
    };
  }
  const triples = [];
  for (let r = 0; r < n; r++) {
    for (let p = halfView.rp[r]; p < halfView.rp[r + 1]; p++) {
      const c = halfView.cols[p];
      const a = halfView.vals[p];
      triples.push([r, c, a]);
      if (r !== c) triples.push([c, r, a]);
    }
  }
  return triplesToView(triples, n, false, halfView);
}
EOF

cat > "/app/environment/q5r/src/lane_c.mjs" <<'EOF'
export function fn_q5(view, x, tiles) {
  const n = view.dim;
  const y = new Float64Array(n);
  const t = Math.max(1, tiles | 0);
  for (let base = 0; base < n; base += t) {
    const hi = Math.min(n, base + t);
    for (let r = base; r < hi; r++) {
      let s = 0;
      for (let p = view.rp[r]; p < view.rp[r + 1]; p++) {
        s += view.vals[p] * x[view.cols[p]];
      }
      y[r] = s;
    }
  }
  return y;
}
EOF

cat > "/app/environment/z2m/src/lane_d.mjs" <<'EOF'
import fs from "node:fs";
import path from "node:path";
import {
  l2,
  l2norm,
  traceDigest,
  viewDigest,
} from "../../common/view.mjs";

let mono = 0;

export function fn_z2(view, caps, outPaths) {
  const y = caps.probe_y;
  const yRef = caps.y_ref;
  const rAbs = l2(y, yRef);
  const rRel = rAbs / Math.max(l2norm(yRef), 1e-300);
  const slot = {
    pack_id: view.pack_id,
    dim: view.dim,
    nz_live: view.vals.length,
    nz_cap: caps.nz_cap,
    view_digest: viewDigest(view),
  };
  const band = {
    pack_id: view.pack_id,
    r_abs: rAbs,
    r_rel: rRel,
    abs_band: view.abs_band,
    rel_band: view.rel_band,
    trace_digest: traceDigest(y),
  };
  fs.mkdirSync(path.dirname(outPaths.slot), { recursive: true });
  fs.writeFileSync(outPaths.slot, JSON.stringify(slot, null, 2));
  fs.writeFileSync(outPaths.band, JSON.stringify(band, null, 2));
  mono += 1;
  const line = {
    pack_id: view.pack_id,
    nz_live: slot.nz_live,
    r_abs: band.r_abs,
    r_rel: band.r_rel,
    trace_digest: band.trace_digest,
    ts_mono: mono,
  };
  fs.appendFileSync(outPaths.log, JSON.stringify(line) + "\n");
  return { slot, band };
}
EOF

mkdir -p /app/output
# smoke all packs after patch
node "/app/environment/tools/drive_a.mjs" --pack s1
node "/app/environment/tools/drive_a.mjs" --pack s2
node "/app/environment/tools/drive_a.mjs" --pack s3
