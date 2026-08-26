#!/bin/bash
set -euo pipefail

# Rebuild the line-shape engine over the whole plane. Above the axis w(z) is
# bounded and Weideman's rational approximation in plain double is enough.
# Below it, w(z) = 2 exp(-z^2) - w(-z) explodes like exp(y^2 - x^2), so the
# engine works in log space, and the graded absolute bars (5e-9 on ln|w| whose
# magnitude reaches 9e14, and on a phase whose unreduced value reaches 1.8e15)
# sit far below double spacing at that size. The square difference, the phase
# product, its reduction mod 2*pi, and the printing of the log-modulus are all
# carried in double-double built from error-free transforms. The whole program
# is written to /app/faddeeva.js.

cat > /app/faddeeva.js <<'JS'
'use strict';

// Full-plane Faddeeva line-shape engine: for each request z = x + i*y the
// program prints ln|w(z)| and arg(w(z)) on one line, space separated.
//
//   node faddeeva.js <requests.jsonl>
//
// Below the real axis w explodes like exp(y^2 - x^2), so everything is done in
// log space through the reflection w(z) = 2 exp(-z^2) - w(-z). The graded bar
// is 5e-9 ABSOLUTE on ln|w| whose magnitude reaches 9e14, and the same bar on
// the phase whose unreduced value 2xy reaches 1.8e15. Neither survives plain
// double arithmetic: the spacing of doubles at 1e15 is about 0.1. The squares,
// their difference, the phase product, and its reduction mod 2pi are therefore
// carried in double-double (hi + lo pairs, ~32 significant digits), and the
// final log-modulus is printed from the pair, not from a collapsed double.

// ---------- double-double primitives ----------

function twoSum(a, b) {
  const s = a + b;
  const bb = s - a;
  const e = (a - (s - bb)) + (b - bb);
  return [s, e];
}

function quickTwoSum(a, b) {  // requires |a| >= |b|
  const s = a + b;
  return [s, b - (s - a)];
}

const SPLIT = 134217729; // 2^27 + 1

function twoProd(a, b) {
  const p = a * b;
  const aa = SPLIT * a, ah = aa - (aa - a), al = a - ah;
  const bb = SPLIT * b, bh = bb - (bb - b), bl = b - bh;
  const e = ((ah * bh - p) + ah * bl + al * bh) + al * bl;
  return [p, e];
}

function ddAdd(a, b) {
  const [s, e] = twoSum(a[0], b[0]);
  return quickTwoSum(s, e + a[1] + b[1]);
}

function ddAddD(a, b) {
  const [s, e] = twoSum(a[0], b);
  return quickTwoSum(s, e + a[1]);
}

function ddNeg(a) { return [-a[0], -a[1]]; }

function ddSub(a, b) { return ddAdd(a, ddNeg(b)); }

function ddVal(a) { return a[0] + a[1]; }

// ---------- exact square difference and phase ----------

function ddSquare(v) {
  return twoProd(v, v);
}

// y^2 - x^2 as a double-double: the two products are exact, the subtraction
// keeps the cancellation instead of rounding it away.
function squareDiff(x, y) {
  return ddSub(ddSquare(y), ddSquare(x));
}

// -2xy as a double-double (twoProd is exact, scaling by -2 is exact)
function phaseRaw(x, y) {
  const [p, e] = twoProd(x, y);
  return [-2 * p, -2 * e];
}

// 2*pi as three non-overlapping doubles (about 48 significant digits)
const TP0 = 6.283185307179586;
const TP1 = 2.4492935982947064e-16;
const TP2 = -5.9895396194366793e-33;

// Reduce a double-double angle into (-pi, pi]. |p| can reach 1.8e15, so the
// multiple n is still an exact integer double; n times each part of the
// three-part 2*pi is subtracted in dd, which keeps the residual to ~1e-16.
function reducePhase(p) {
  const n = Math.round(ddVal(p) / TP0);
  if (n !== 0) {
    let acc = ddSub(p, twoProd(n, TP0));
    acc = ddSub(acc, twoProd(n, TP1));
    acc = ddAddD(acc, -(n * TP2));
    p = acc;
  }
  let r = ddVal(p);
  if (r > Math.PI) r -= TP0;
  if (r <= -Math.PI) r += TP0;
  return r;
}

function wrapPi(a) {
  while (a > Math.PI) a -= TP0;
  while (a <= -Math.PI) a += TP0;
  return a;
}

// ---------- Weideman rational approximation, upper half-plane ----------

const N = 44;
const M = 2 * N;
const M2 = 2 * M;
const L = Math.sqrt(N / Math.SQRT2);
const INV_SQRT_PI = 1 / Math.sqrt(Math.PI);

function buildCoeffs() {
  const f = new Float64Array(M2);
  f[0] = 0;
  let idx = 1;
  for (let k = -M + 1; k <= M - 1; k++) {
    const t = L * Math.tan((k * Math.PI) / M / 2);
    f[idx++] = Math.exp(-t * t) * (L * L + t * t);
  }
  const half = M2 / 2;
  const fs = new Float64Array(M2);
  for (let i = 0; i < M2; i++) fs[i] = f[(i + half) % M2];
  const coeff = new Float64Array(N);
  for (let m = 1; m <= N; m++) {
    let re = 0;
    for (let n = 0; n < M2; n++) re += fs[n] * Math.cos((-2 * Math.PI * m * n) / M2);
    coeff[N - m] = re / M2;
  }
  return coeff;
}

const A = buildCoeffs();

// w(x + iy) for y >= 0, plain double precision: the function is bounded and
// well conditioned there, so double is enough for this piece.
function weideman(x, y) {
  const denRe = L + y, denIm = -x;
  const numRe = L - y, numIm = x;
  const d = denRe * denRe + denIm * denIm;
  const Zre = (numRe * denRe + numIm * denIm) / d;
  const Zim = (numIm * denRe - numRe * denIm) / d;
  let pRe = A[0], pIm = 0;
  for (let i = 1; i < N; i++) {
    const nr = pRe * Zre - pIm * Zim + A[i];
    const ni = pRe * Zim + pIm * Zre;
    pRe = nr; pIm = ni;
  }
  const sqRe = denRe * denRe - denIm * denIm;
  const sqIm = 2 * denRe * denIm;
  const sq2 = sqRe * sqRe + sqIm * sqIm;
  const t1Re = (2 * (pRe * sqRe + pIm * sqIm)) / sq2;
  const t1Im = (2 * (pIm * sqRe - pRe * sqIm)) / sq2;
  const t2Re = (INV_SQRT_PI * denRe) / d;
  const t2Im = (-INV_SQRT_PI * denIm) / d;
  return [t1Re + t2Re, t1Im + t2Im];
}

// ---------- printing a double-double log-modulus ----------

// The integer part of |V| stays below 2^53 for the graded ranges, so it is an
// exact double and prints exactly; the fractional part is printed from the
// residual pair. Collapsing V to one double first would lose everything under
// ~0.1 at the largest magnitudes.
function formatDD(v) {
  let sign = '';
  if (ddVal(v) < 0) { sign = '-'; v = ddNeg(v); }
  let ip = Math.floor(v[0]);
  const frac = ddAddD(v, -ip); // exact: ip has no fractional bits
  let f = ddVal(frac);
  if (f < 0) { ip -= 1; f += 1; }
  if (f >= 1) { ip += 1; f -= 1; }
  let fs = f.toFixed(15);
  if (fs[0] === '1') { ip += 1; fs = '0.000000000000000'; }
  return sign + String(ip) + fs.slice(1);
}

// ---------- full-plane evaluation ----------

const LN2 = Math.log(2);

function evaluate(x, y) {
  if (y >= 0) {
    const [re, im] = weideman(x, y);
    const lnmod = Math.log(Math.hypot(re, im));
    const ang = Math.atan2(im, re);
    return [[lnmod, 0], ang];
  }
  // reflection: w(z) = 2 exp(-z^2) - w(-z), with -z in the upper half-plane.
  // log of the first term: [ln2 + (y^2 - x^2)] + i*(-2xy), real part in dd.
  const D = squareDiff(x, y);
  const Add = ddAddD(D, LN2);
  const phiA = reducePhase(phaseRaw(x, y));
  const [ur, ui] = weideman(-x, -y);
  const lnu = Math.log(Math.hypot(ur, ui));
  const theta = Math.atan2(ui, ur);
  // g = ln|w(-z)| - ln|2 exp(-z^2)|; only its double value matters below
  const g = lnu - ddVal(Add);
  if (g < -45) {
    // exploding side: the reflection correction is below 1e-19 relative
    return [Add, phiA];
  }
  if (g > 45) {
    // reflection-dominated side: 2 exp(-z^2) is below 1e-19 relative
    return [[lnu, 0], wrapPi(theta + Math.PI)];
  }
  // both terms in play: w = 2 exp(-z^2) * (1 - rho e^{i delta})
  const rho = Math.exp(g);
  const delta = wrapPi(theta - phiA);
  const sRe = 1 - rho * Math.cos(delta);
  const sIm = -rho * Math.sin(delta);
  const lnmod = ddAddD(Add, Math.log(Math.hypot(sRe, sIm)));
  const ang = wrapPi(phiA + Math.atan2(sIm, sRe));
  return [lnmod, ang];
}

function main() {
  const path = process.argv[2];
  if (!path) { process.stderr.write('usage: node faddeeva.js <requests.jsonl>\n'); process.exit(2); }
  const fs = require('fs');
  const data = fs.readFileSync(path, 'utf8');
  const out = [];
  for (const line of data.split('\n')) {
    const s = line.trim();
    if (!s) continue;
    const req = JSON.parse(s);
    const [lnmod, ang] = evaluate(req.x, req.y);
    out.push(formatDD(lnmod) + ' ' + ang.toPrecision(17));
  }
  process.stdout.write(out.join('\n') + '\n');
}

main();
JS

echo "wrote /app/faddeeva.js"
node /app/faddeeva.js /app/requests.jsonl | head -n 3
