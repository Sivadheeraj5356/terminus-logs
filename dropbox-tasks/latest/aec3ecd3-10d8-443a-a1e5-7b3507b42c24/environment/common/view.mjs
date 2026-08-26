import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

export function readMeta(dir) {
  const text = fs.readFileSync(path.join(dir, "meta.toml"), "utf8");
  const out = {};
  for (const line of text.split("\n")) {
    const m = line.match(/^([A-Za-z0-9_]+)\s*=\s*(.+)$/);
    if (!m) continue;
    let v = m[2].trim();
    if (v === "true") out[m[1]] = true;
    else if (v === "false") out[m[1]] = false;
    else if (/^-?\d+(\.\d+)?([eE][+-]?\d+)?$/.test(v)) out[m[1]] = Number(v);
    else out[m[1]] = v.replace(/^"|"$/g, "");
  }
  return out;
}

export function loadView(dir) {
  const meta = readMeta(dir);
  const n = meta.dim;
  const vb = fs.readFileSync(path.join(dir, "values.bin"));
  const cb = fs.readFileSync(path.join(dir, "col.bin"));
  const rb = fs.readFileSync(path.join(dir, "idx.bin"));
  const vals = new Float64Array(vb.buffer, vb.byteOffset, vb.byteLength / 8);
  const cols = new Uint32Array(cb.buffer, cb.byteOffset, cb.byteLength / 4);
  const rp = new Uint32Array(rb.buffer, rb.byteOffset, rb.byteLength / 4);
  return {
    dim: n,
    half: !!meta.half,
    vals: Float64Array.from(vals),
    cols: Uint32Array.from(cols),
    rp: Uint32Array.from(rp),
    abs_band: meta.abs_band,
    rel_band: meta.rel_band,
    x_seed: meta.x_seed,
    pack_id: meta.name || path.basename(dir),
  };
}

export function cloneView(v) {
  return {
    dim: v.dim,
    half: v.half,
    vals: Float64Array.from(v.vals),
    cols: Uint32Array.from(v.cols),
    rp: Uint32Array.from(v.rp),
    abs_band: v.abs_band,
    rel_band: v.rel_band,
    x_seed: v.x_seed,
    pack_id: v.pack_id,
  };
}

export function makeX(dim, seed) {
  const x = new Float64Array(dim);
  for (let i = 0; i < dim; i++) {
    x[i] = 1.0 + 0.1 * ((i + seed) % 97);
  }
  return x;
}

export function fullFromHalf(view) {
  const n = view.dim;
  const triples = [];
  for (let r = 0; r < n; r++) {
    for (let p = view.rp[r]; p < view.rp[r + 1]; p++) {
      const c = view.cols[p];
      const a = view.vals[p];
      triples.push([r, c, a]);
      if (r !== c) triples.push([c, r, a]);
    }
  }
  return triplesToView(triples, n, false, view);
}

export function triplesToView(triples, n, half, proto) {
  const map = new Map();
  for (const [i, j, a] of triples) {
    if (half && i > j) continue;
    const k = i * n + j;
    map.set(k, (map.get(k) || 0) + a);
  }
  const rows = [...map.entries()]
    .map(([k, a]) => [Math.floor(k / n), k % n, a])
    .sort((u, v) => (u[0] - v[0]) || (u[1] - v[1]));
  const vals = new Float64Array(rows.length);
  const cols = new Uint32Array(rows.length);
  const rp = new Uint32Array(n + 1);
  for (const [i, j, a] of rows) {
    rp[i + 1] += 1;
  }
  for (let i = 0; i < n; i++) rp[i + 1] += rp[i];
  const cursor = Uint32Array.from(rp.subarray(0, n));
  for (const [i, j, a] of rows) {
    const p = cursor[i]++;
    vals[p] = a;
    cols[p] = j;
  }
  return {
    dim: n,
    half: !!half,
    vals,
    cols,
    rp,
    abs_band: proto.abs_band,
    rel_band: proto.rel_band,
    x_seed: proto.x_seed,
    pack_id: proto.pack_id,
  };
}

export function productRef(view, x) {
  const full = view.half ? fullFromHalf(view) : view;
  const y = new Float64Array(full.dim);
  for (let r = 0; r < full.dim; r++) {
    let s = 0;
    for (let p = full.rp[r]; p < full.rp[r + 1]; p++) {
      s += full.vals[p] * x[full.cols[p]];
    }
    y[r] = s;
  }
  return y;
}

export function l2(a, b) {
  let s = 0;
  for (let i = 0; i < a.length; i++) {
    const d = a[i] - b[i];
    s += d * d;
  }
  return Math.sqrt(s);
}

export function l2norm(a) {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i] * a[i];
  return Math.sqrt(s);
}

export function viewDigest(view) {
  const h = crypto.createHash("sha256");
  h.update(Buffer.from(view.vals.buffer, view.vals.byteOffset, view.vals.byteLength));
  h.update(Buffer.from(view.cols.buffer, view.cols.byteOffset, view.cols.byteLength));
  h.update(Buffer.from(view.rp.buffer, view.rp.byteOffset, view.rp.byteLength));
  return h.digest("hex");
}

export function traceDigest(y) {
  const h = crypto.createHash("sha256");
  for (let i = 0; i < y.length; i++) {
    h.update(`i=${i};v=${y[i].toFixed(12)}\n`);
  }
  return h.digest("hex");
}

export function readNlim(root) {
  const text = fs.readFileSync(path.join(root, "docs", "nlim.toml"), "utf8");
  const out = {};
  for (const line of text.split("\n")) {
    const m = line.match(/^([A-Za-z0-9_]+)\s*=\s*(.+)$/);
    if (!m) continue;
    out[m[1]] = Number(m[2].trim());
  }
  return out;
}

export function defaultPerm(n) {
  const p = new Uint32Array(n);
  for (let i = 0; i < n; i++) p[i] = i;
  // mild bandwidth-friendly shuffle: odds then evens reversed
  const odd = [];
  const even = [];
  for (let i = 0; i < n; i++) (i % 2 ? odd : even).push(i);
  even.reverse();
  const order = odd.concat(even);
  for (let i = 0; i < n; i++) p[i] = order[i];
  return p;
}
