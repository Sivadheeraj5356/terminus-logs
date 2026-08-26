#!/usr/bin/env bash
# Reference solution: materialize the engine crate, build it offline, and run the
# three canonical modes so /app/out/runs.db is populated.
set -euo pipefail
cd /app

mkdir -p src .cargo out

cat > Cargo.toml <<'EOF_CARGO'
[package]
name = "engine"
version = "0.1.0"
edition = "2021"

[[bin]]
name = "engine"
path = "src/main.rs"

[profile.release]
opt-level = 2
EOF_CARGO

cat > .cargo/config.toml <<'EOF_CFG'
[net]
offline = true
EOF_CFG

cat > src/rng.rs <<'EOF_RNG_RS'
//! Single-word deterministic PRNG (SplitMix64). The whole point is that the
//! entire state is one u64 that can be snapshotted and restored, so a
//! rematerialized forward pass draws exactly the masks it drew the first time.

#[derive(Clone, Copy)]
pub struct Rng {
    s: u64,
}

impl Rng {
    pub fn new(seed: u64) -> Self {
        Rng { s: seed }
    }

    #[inline]
    pub fn next_u64(&mut self) -> u64 {
        self.s = self.s.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.s;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Uniform in the open interval (0, 1); never 0 or 1.
    #[inline]
    pub fn uniform_open(&mut self) -> f64 {
        let x = self.next_u64() >> 11;
        (x as f64 + 0.5) * (1.0 / 9007199254740992.0)
    }

    /// Uniform integer in [0, n) via Lemire multiply-shift; exactly one draw.
    #[inline]
    pub fn below(&mut self, n: u64) -> u64 {
        ((self.next_u64() as u128 * n as u128) >> 64) as u64
    }

    /// Standard normal via Box-Muller (cosine branch); exactly two draws.
    #[inline]
    pub fn normal(&mut self) -> f64 {
        let u1 = self.uniform_open();
        let u2 = self.uniform_open();
        (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos()
    }

    pub fn state(&self) -> u64 {
        self.s
    }

    pub fn set_state(&mut self, s: u64) {
        self.s = s;
    }
}
EOF_RNG_RS

cat > src/tensor.rs <<'EOF_TENSOR_RS'
//! Dense row-major f64 matrix. Reductions are plain sequential loops so the
//! order is fixed and identical between the cached and rematerialized passes.

#[derive(Clone)]
pub struct Mat {
    pub rows: usize,
    pub cols: usize,
    pub data: Vec<f64>,
}

impl Mat {
    pub fn zeros(rows: usize, cols: usize) -> Self {
        Mat { rows, cols, data: vec![0.0; rows * cols] }
    }

    pub fn from_vec(rows: usize, cols: usize, data: Vec<f64>) -> Self {
        assert_eq!(rows * cols, data.len());
        Mat { rows, cols, data }
    }

    #[inline]
    pub fn get(&self, i: usize, j: usize) -> f64 {
        self.data[i * self.cols + j]
    }

    #[inline]
    pub fn set(&mut self, i: usize, j: usize, v: f64) {
        self.data[i * self.cols + j] = v;
    }

    /// self (rows x k) * other (k x cols); accumulate over k in order.
    pub fn matmul(&self, other: &Mat) -> Mat {
        assert_eq!(self.cols, other.rows);
        let (r, k, c) = (self.rows, self.cols, other.cols);
        let mut out = Mat::zeros(r, c);
        for i in 0..r {
            for j in 0..c {
                let mut acc = 0.0;
                for kk in 0..k {
                    acc += self.get(i, kk) * other.get(kk, j);
                }
                out.set(i, j, acc);
            }
        }
        out
    }

    pub fn transpose(&self) -> Mat {
        let mut out = Mat::zeros(self.cols, self.rows);
        for i in 0..self.rows {
            for j in 0..self.cols {
                out.set(j, i, self.get(i, j));
            }
        }
        out
    }

    /// Add a length-cols bias vector to every row.
    pub fn add_row_bias(&mut self, bias: &[f64]) {
        assert_eq!(bias.len(), self.cols);
        for i in 0..self.rows {
            for j in 0..self.cols {
                self.data[i * self.cols + j] += bias[j];
            }
        }
    }

    /// Column sums (length cols), sequential over rows.
    pub fn col_sums(&self) -> Vec<f64> {
        let mut out = vec![0.0; self.cols];
        for i in 0..self.rows {
            for j in 0..self.cols {
                out[j] += self.get(i, j);
            }
        }
        out
    }

    pub fn sq_sum(&self) -> f64 {
        let mut acc = 0.0;
        for &v in &self.data {
            acc += v * v;
        }
        acc
    }
}
EOF_TENSOR_RS

cat > src/ops.rs <<'EOF_OPS_RS'
//! Forward/backward for the individual ops. Formulas mirror engine_design.md.

use crate::tensor::Mat;

pub struct LnCache {
    pub xhat: Mat,
    pub inv: Vec<f64>,
    pub gamma: Vec<f64>,
}

pub fn layernorm_fwd(z: &Mat, gamma: &[f64], beta: &[f64], eps: f64) -> (Mat, LnCache) {
    let (r, h) = (z.rows, z.cols);
    let mut y = Mat::zeros(r, h);
    let mut xhat = Mat::zeros(r, h);
    let mut inv = vec![0.0; r];
    for i in 0..r {
        let mut mu = 0.0;
        for j in 0..h {
            mu += z.get(i, j);
        }
        mu /= h as f64;
        let mut var = 0.0;
        for j in 0..h {
            let d = z.get(i, j) - mu;
            var += d * d;
        }
        var /= h as f64;
        let iv = 1.0 / (var + eps).sqrt();
        inv[i] = iv;
        for j in 0..h {
            let xh = (z.get(i, j) - mu) * iv;
            xhat.set(i, j, xh);
            y.set(i, j, xh * gamma[j] + beta[j]);
        }
    }
    (y, LnCache { xhat, inv, gamma: gamma.to_vec() })
}

pub fn layernorm_bwd(dy: &Mat, c: &LnCache) -> (Mat, Vec<f64>, Vec<f64>) {
    let (r, h) = (dy.rows, dy.cols);
    let mut dgamma = vec![0.0; h];
    let mut dbeta = vec![0.0; h];
    for i in 0..r {
        for j in 0..h {
            dgamma[j] += dy.get(i, j) * c.xhat.get(i, j);
            dbeta[j] += dy.get(i, j);
        }
    }
    let mut dz = Mat::zeros(r, h);
    for i in 0..r {
        // dxhat = dy * gamma ; reduce sums over the feature axis in order
        let mut sum_dxhat = 0.0;
        let mut sum_dxhat_xhat = 0.0;
        for j in 0..h {
            let dxhat = dy.get(i, j) * c.gamma[j];
            sum_dxhat += dxhat;
            sum_dxhat_xhat += dxhat * c.xhat.get(i, j);
        }
        let coef = c.inv[i] / h as f64;
        for j in 0..h {
            let dxhat = dy.get(i, j) * c.gamma[j];
            let v = coef * (h as f64 * dxhat - sum_dxhat - c.xhat.get(i, j) * sum_dxhat_xhat);
            dz.set(i, j, v);
        }
    }
    (dz, dgamma, dbeta)
}

pub fn relu_fwd(z: &Mat) -> Mat {
    let mut out = z.clone();
    for v in out.data.iter_mut() {
        if *v < 0.0 {
            *v = 0.0;
        }
    }
    out
}

/// dz = dy where the relu output was > 0, else 0.
pub fn relu_bwd(dy: &Mat, a: &Mat) -> Mat {
    let mut out = Mat::zeros(dy.rows, dy.cols);
    for idx in 0..dy.data.len() {
        out.data[idx] = if a.data[idx] > 0.0 { dy.data[idx] } else { 0.0 };
    }
    out
}

/// Layer-3 activation: z^3 / 3 (derivative z^2). Intentionally amplifying.
pub fn unstable_fwd(z: &Mat) -> Mat {
    let mut out = Mat::zeros(z.rows, z.cols);
    for i in 0..z.data.len() {
        let v = z.data[i];
        out.data[i] = v * v * v / 3.0;
    }
    out
}

pub fn unstable_bwd(z: &Mat, da: &Mat) -> Mat {
    let mut out = Mat::zeros(z.rows, z.cols);
    for i in 0..z.data.len() {
        let v = z.data[i];
        out.data[i] = da.data[i] * v * v;
    }
    out
}

/// Elementwise multiply (dropout apply / mask backward).
pub fn hadamard(a: &Mat, b: &Mat) -> Mat {
    let mut out = Mat::zeros(a.rows, a.cols);
    for i in 0..a.data.len() {
        out.data[i] = a.data[i] * b.data[i];
    }
    out
}

/// Mean softmax cross-entropy over the batch. Returns (loss, dlogits).
pub fn softmax_ce(logits: &Mat, targets: &[usize]) -> (f64, Mat) {
    let (r, c) = (logits.rows, logits.cols);
    let mut d = Mat::zeros(r, c);
    let mut loss = 0.0;
    for i in 0..r {
        let mut m = logits.get(i, 0);
        for j in 1..c {
            let v = logits.get(i, j);
            if v > m {
                m = v;
            }
        }
        let mut denom = 0.0;
        for j in 0..c {
            denom += (logits.get(i, j) - m).exp();
        }
        for j in 0..c {
            let p = (logits.get(i, j) - m).exp() / denom;
            d.set(i, j, p);
        }
        let t = targets[i];
        loss += -(d.get(i, t)).ln();
        d.set(i, t, d.get(i, t) - 1.0);
    }
    for v in d.data.iter_mut() {
        *v /= r as f64;
    }
    (loss / r as f64, d)
}
EOF_OPS_RS

cat > src/tape.rs <<'EOF_TAPE_RS'
//! The autodiff tape: parameters, the forward activation record, and the
//! reverse pass. Layer 2's block is the one rematerialized on the backward pass.

use crate::ops::*;
use crate::rng::Rng;
use crate::tensor::Mat;

// ---- architecture / spec-pinned hyperparameters ----
pub const H1: usize = 16;
pub const H2: usize = 16;
pub const H3: usize = 16;
pub const EPOCHS: usize = 4;
pub const DROPOUT_P: f64 = 0.2;
pub const LR: f64 = 0.01;
pub const BETA1: f64 = 0.9;
pub const BETA2: f64 = 0.999;
pub const EPS: f64 = 1e-8;
pub const LN_EPS: f64 = 1e-5;
pub const CLIP_TAU: f64 = 3.0;
pub const SIG_W1: f64 = 0.30;
pub const SIG_W2: f64 = 0.30;
pub const SIG_W3: f64 = 0.50;
pub const SIG_WO: f64 = 0.30;

pub const N_TENSORS: usize = 12;

/// Parameters (also reused as the gradient container). Vectors are stored as
/// 1 x len matrices so every tensor can be iterated uniformly.
#[derive(Clone)]
pub struct Params {
    pub w1: Mat, pub b1: Mat, pub g1: Mat, pub be1: Mat,
    pub w2: Mat, pub b2: Mat, pub g2: Mat, pub be2: Mat,
    pub w3: Mat, pub b3: Mat,
    pub wo: Mat, pub bo: Mat,
}

pub type Grads = Params;

impl Params {
    pub fn zeros(d_in: usize, c: usize) -> Self {
        Params {
            w1: Mat::zeros(d_in, H1), b1: Mat::zeros(1, H1),
            g1: Mat::zeros(1, H1), be1: Mat::zeros(1, H1),
            w2: Mat::zeros(H1, H2), b2: Mat::zeros(1, H2),
            g2: Mat::zeros(1, H2), be2: Mat::zeros(1, H2),
            w3: Mat::zeros(H2, H3), b3: Mat::zeros(1, H3),
            wo: Mat::zeros(H3, c), bo: Mat::zeros(1, c),
        }
    }

    /// Canonical order: W1,b1,g1,be1,W2,b2,g2,be2,W3,b3,Wo,bo.
    pub fn tensors(&self) -> [&Mat; N_TENSORS] {
        [&self.w1, &self.b1, &self.g1, &self.be1,
         &self.w2, &self.b2, &self.g2, &self.be2,
         &self.w3, &self.b3, &self.wo, &self.bo]
    }

    pub fn tensors_mut(&mut self) -> [&mut Mat; N_TENSORS] {
        [&mut self.w1, &mut self.b1, &mut self.g1, &mut self.be1,
         &mut self.w2, &mut self.b2, &mut self.g2, &mut self.be2,
         &mut self.w3, &mut self.b3, &mut self.wo, &mut self.bo]
    }

    pub fn init(rng: &mut Rng, d_in: usize, c: usize) -> Self {
        let mut p = Params::zeros(d_in, c);
        fill_normal(&mut p.w1, rng, SIG_W1);
        // b1, g1, be1: biases zero, gamma one, beta zero
        set_all(&mut p.g1, 1.0);
        fill_normal(&mut p.w2, rng, SIG_W2);
        set_all(&mut p.g2, 1.0);
        fill_normal(&mut p.w3, rng, SIG_W3);
        fill_normal(&mut p.wo, rng, SIG_WO);
        p
    }
}

fn fill_normal(m: &mut Mat, rng: &mut Rng, sig: f64) {
    // row-major draw order
    for i in 0..m.data.len() {
        m.data[i] = rng.normal() * sig;
    }
}

fn set_all(m: &mut Mat, v: f64) {
    for x in m.data.iter_mut() {
        *x = v;
    }
}

fn draw_mask(rng: &mut Rng, rows: usize, width: usize) -> Mat {
    let mut m = Mat::zeros(rows, width);
    let scale = 1.0 / (1.0 - DROPOUT_P);
    for i in 0..rows {
        for j in 0..width {
            let u = rng.uniform_open();
            m.data[i * width + j] = if u >= DROPOUT_P { scale } else { 0.0 };
        }
    }
    m
}

pub struct Tape {
    pub x: Mat,
    pub c1: LnCache,
    pub a1: Mat,
    pub m1: Mat,
    pub d1: Mat,
    pub rng_pre: u64,
    // layer-2 block: present only when not rematerialized
    pub c2: Option<LnCache>,
    pub a2: Option<Mat>,
    pub m2: Option<Mat>,
    pub d2: Option<Mat>,
    pub z3: Mat,
    pub a3: Mat,
    pub zo: Mat,
}

pub fn forward(p: &Params, x: &Mat, rng: &mut Rng, remat: bool) -> Tape {
    let z1 = {
        let mut z = x.matmul(&p.w1);
        z.add_row_bias(&p.b1.data);
        z
    };
    let (ln1, c1) = layernorm_fwd(&z1, &p.g1.data, &p.be1.data, LN_EPS);
    let a1 = relu_fwd(&ln1);
    let r = x.rows;
    let m1 = draw_mask(rng, r, H1);
    let d1 = hadamard(&a1, &m1);
    let rng_pre = rng.state();
    let mut z2 = d1.matmul(&p.w2);
    z2.add_row_bias(&p.b2.data);
    let (ln2, c2) = layernorm_fwd(&z2, &p.g2.data, &p.be2.data, LN_EPS);
    let a2 = relu_fwd(&ln2);
    let m2 = draw_mask(rng, r, H2);
    let d2 = hadamard(&a2, &m2);
    let mut z3 = d2.matmul(&p.w3);
    z3.add_row_bias(&p.b3.data);
    let a3 = unstable_fwd(&z3);
    let mut zo = a3.matmul(&p.wo);
    zo.add_row_bias(&p.bo.data);
    Tape {
        x: x.clone(), c1, a1, m1, d1, rng_pre,
        c2: if remat { None } else { Some(c2) },
        a2: if remat { None } else { Some(a2) },
        m2: if remat { None } else { Some(m2) },
        d2: if remat { None } else { Some(d2) },
        z3, a3, zo,
    }
}

/// Reverse pass. In remat mode the layer-2 block is recomputed from d1 with the
/// PRNG restored to `rng_pre` so the same dropout mask is regenerated; the main
/// stream is left untouched.
pub fn backward(p: &Params, tape: &Tape, dlogits: &Mat, rng: &mut Rng, remat: bool) -> Grads {
    let d_in = p.w1.rows;
    let c = p.wo.cols;
    let mut g = Params::zeros(d_in, c);

    // output layer
    g.wo = tape.a3.transpose().matmul(dlogits);
    g.bo = Mat::from_vec(1, c, dlogits.col_sums());
    let da3 = dlogits.matmul(&p.wo.transpose());
    let dz3 = unstable_bwd(&tape.z3, &da3);

    // recover the layer-2 block
    let (c2, a2, m2, d2): (LnCache, Mat, Mat, Mat) = if remat {
        let main = rng.state();
        rng.set_state(tape.rng_pre);
        let mut z2 = tape.d1.matmul(&p.w2);
        z2.add_row_bias(&p.b2.data);
        let (ln2, c2) = layernorm_fwd(&z2, &p.g2.data, &p.be2.data, LN_EPS);
        let a2 = relu_fwd(&ln2);
        let m2 = draw_mask(rng, tape.d1.rows, H2);
        let d2 = hadamard(&a2, &m2);
        rng.set_state(main);
        (c2, a2, m2, d2)
    } else {
        (
            clone_cache(tape.c2.as_ref().unwrap()),
            tape.a2.clone().unwrap(),
            tape.m2.clone().unwrap(),
            tape.d2.clone().unwrap(),
        )
    };

    g.w3 = d2.transpose().matmul(&dz3);
    g.b3 = Mat::from_vec(1, H3, dz3.col_sums());
    let dd2 = dz3.matmul(&p.w3.transpose());
    let da2 = hadamard(&dd2, &m2);
    let dln2 = relu_bwd(&da2, &a2);
    let (dz2, dg2, dbe2) = layernorm_bwd(&dln2, &c2);
    g.g2 = Mat::from_vec(1, H2, dg2);
    g.be2 = Mat::from_vec(1, H2, dbe2);
    g.w2 = tape.d1.transpose().matmul(&dz2);
    g.b2 = Mat::from_vec(1, H2, dz2.col_sums());
    let dd1 = dz2.matmul(&p.w2.transpose());
    let da1 = hadamard(&dd1, &tape.m1);
    let dln1 = relu_bwd(&da1, &tape.a1);
    let (dz1, dg1, dbe1) = layernorm_bwd(&dln1, &tape.c1);
    g.g1 = Mat::from_vec(1, H1, dg1);
    g.be1 = Mat::from_vec(1, H1, dbe1);
    g.w1 = tape.x.transpose().matmul(&dz1);
    g.b1 = Mat::from_vec(1, H1, dz1.col_sums());
    g
}

fn clone_cache(c: &LnCache) -> LnCache {
    LnCache { xhat: c.xhat.clone(), inv: c.inv.clone(), gamma: c.gamma.clone() }
}

/// Global-norm clip of the layer-3 gradient group (W3,b3) only. Returns the
/// pre-clip norm.
pub fn clip_layer3(g: &mut Grads) -> f64 {
    let n = (g.w3.sq_sum() + g.b3.sq_sum()).sqrt();
    if n > CLIP_TAU {
        let s = CLIP_TAU / n;
        for v in g.w3.data.iter_mut() {
            *v *= s;
        }
        for v in g.b3.data.iter_mut() {
            *v *= s;
        }
    }
    n
}

/// L2 norm over all gradients, in canonical tensor order.
pub fn global_norm(g: &Grads) -> f64 {
    let mut tot = 0.0;
    for t in g.tensors() {
        tot += t.sq_sum();
    }
    tot.sqrt()
}
EOF_TAPE_RS

cat > src/optimizer.rs <<'EOF_OPTIMIZER_RS'
//! Adam with the epsilon placed OUTSIDE the sqrt: p -= lr * mhat / (sqrt(vhat) + eps).

use crate::tape::{Grads, Params, BETA1, BETA2, EPS, LR, N_TENSORS};

pub struct Adam {
    pub m: Params,
    pub v: Params,
    pub t: u64,
}

impl Adam {
    pub fn new(d_in: usize, c: usize) -> Self {
        Adam { m: Params::zeros(d_in, c), v: Params::zeros(d_in, c), t: 0 }
    }

    pub fn step(&mut self, p: &mut Params, g: &Grads) {
        self.t += 1;
        let t = self.t as i32;
        let bc1 = 1.0 - BETA1.powi(t);
        let bc2 = 1.0 - BETA2.powi(t);
        let ms = self.m.tensors_mut();
        let vs = self.v.tensors_mut();
        let ps = p.tensors_mut();
        let gs = g.tensors();
        for i in 0..N_TENSORS {
            let n = gs[i].data.len();
            for j in 0..n {
                let grad = gs[i].data[j];
                let mnew = BETA1 * ms[i].data[j] + (1.0 - BETA1) * grad;
                let vnew = BETA2 * vs[i].data[j] + (1.0 - BETA2) * grad * grad;
                ms[i].data[j] = mnew;
                vs[i].data[j] = vnew;
                let mhat = mnew / bc1;
                let vhat = vnew / bc2;
                ps[i].data[j] -= LR * mhat / (vhat.sqrt() + EPS);
            }
        }
    }
}
EOF_OPTIMIZER_RS

cat > src/dataset.rs <<'EOF_DATASET_RS'
//! Config parsing (a tiny TOML subset) and raw dataset loading.

use crate::tensor::Mat;
use std::collections::HashMap;
use std::fs;

/// Parse `key = value` lines into a string->string map. Handles inline comments,
/// double-quoted strings, hex ints, decimal ints/floats and booleans.
pub fn parse_scalars(path: &str) -> Result<HashMap<String, String>, String> {
    let text = fs::read_to_string(path).map_err(|e| format!("read {path}: {e}"))?;
    let mut out = HashMap::new();
    for line in text.lines() {
        let line = match line.find('#') {
            Some(i) => &line[..i],
            None => line,
        };
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let eq = match line.find('=') {
            Some(i) => i,
            None => continue,
        };
        let key = line[..eq].trim().to_string();
        let mut val = line[eq + 1..].trim().to_string();
        if val.starts_with('"') && val.ends_with('"') && val.len() >= 2 {
            val = val[1..val.len() - 1].to_string();
        }
        out.insert(key, val);
    }
    Ok(out)
}

fn get<'a>(m: &'a HashMap<String, String>, k: &str, path: &str) -> Result<&'a String, String> {
    m.get(k).ok_or_else(|| format!("{path}: missing key `{k}`"))
}

fn parse_u64(s: &str) -> Result<u64, String> {
    let s = s.trim();
    if let Some(hex) = s.strip_prefix("0x").or_else(|| s.strip_prefix("0X")) {
        u64::from_str_radix(hex, 16).map_err(|e| format!("bad hex `{s}`: {e}"))
    } else {
        s.parse::<u64>().map_err(|e| format!("bad int `{s}`: {e}"))
    }
}

pub struct Manifest {
    pub num_samples: usize,
    pub input_dim: usize,
    pub num_classes: usize,
    pub batch_size: usize,
}

pub fn load_manifest(path: &str) -> Result<Manifest, String> {
    let m = parse_scalars(path)?;
    Ok(Manifest {
        num_samples: parse_u64(get(&m, "num_samples", path)?)? as usize,
        input_dim: parse_u64(get(&m, "input_dim", path)?)? as usize,
        num_classes: parse_u64(get(&m, "num_classes", path)?)? as usize,
        batch_size: parse_u64(get(&m, "batch_size", path)?)? as usize,
    })
}

pub fn load_seed(path: &str) -> Result<u64, String> {
    let m = parse_scalars(path)?;
    parse_u64(get(&m, "seed", path)?)
}

pub fn load_resume_step(path: &str) -> Result<usize, String> {
    let m = parse_scalars(path)?;
    Ok(parse_u64(get(&m, "resume_step", path)?)? as usize)
}

pub struct Data {
    pub x: Mat,
    pub y: Vec<usize>,
}

pub fn load_data(inputs: &str, targets: &str, n: usize, d: usize) -> Result<Data, String> {
    let ib = fs::read(inputs).map_err(|e| format!("read {inputs}: {e}"))?;
    if ib.len() != n * d * 8 {
        return Err(format!("{inputs}: expected {} bytes, got {}", n * d * 8, ib.len()));
    }
    let mut xd = Vec::with_capacity(n * d);
    for c in ib.chunks_exact(8) {
        let arr: [u8; 8] = c.try_into().unwrap();
        xd.push(f64::from_le_bytes(arr));
    }
    let tb = fs::read(targets).map_err(|e| format!("read {targets}: {e}"))?;
    if tb.len() != n * 8 {
        return Err(format!("{targets}: expected {} bytes, got {}", n * 8, tb.len()));
    }
    let mut y = Vec::with_capacity(n);
    for c in tb.chunks_exact(8) {
        let arr: [u8; 8] = c.try_into().unwrap();
        let v = i64::from_le_bytes(arr);
        if v < 0 {
            return Err(format!("{targets}: negative label {v}"));
        }
        y.push(v as usize);
    }
    Ok(Data { x: Mat::from_vec(n, d, xd), y })
}
EOF_DATASET_RS

cat > src/checkpoint.rs <<'EOF_CHECKPOINT_RS'
//! Resumable snapshots (weights + optimizer accumulators + PRNG state + step)
//! and the state-fingerprint hashes recorded in the database.

use crate::optimizer::Adam;
use crate::tape::Params;
use std::fs;

const MAGIC: &[u8; 8] = b"CKPTAD01";

pub fn fnv1a64(bytes: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01B3);
    }
    h
}

pub fn hex16(h: u64) -> String {
    format!("{:016x}", h)
}

fn append_params(buf: &mut Vec<u8>, p: &Params) {
    for t in p.tensors() {
        for &x in &t.data {
            buf.extend_from_slice(&x.to_le_bytes());
        }
    }
}

pub fn weights_bytes(p: &Params) -> Vec<u8> {
    let mut b = Vec::new();
    append_params(&mut b, p);
    b
}

pub fn optimizer_bytes(a: &Adam) -> Vec<u8> {
    let mut b = Vec::new();
    append_params(&mut b, &a.m);
    append_params(&mut b, &a.v);
    b.extend_from_slice(&a.t.to_le_bytes());
    b
}

pub fn weights_hash(p: &Params) -> String {
    hex16(fnv1a64(&weights_bytes(p)))
}

pub fn optimizer_hash(a: &Adam) -> String {
    hex16(fnv1a64(&optimizer_bytes(a)))
}

pub fn rng_hash(rng_state: u64) -> String {
    hex16(fnv1a64(&rng_state.to_le_bytes()))
}

/// Fingerprint of the full training state (weights + optimizer + rng).
pub fn full_hash(p: &Params, a: &Adam, rng_state: u64) -> String {
    let mut b = weights_bytes(p);
    b.extend_from_slice(&optimizer_bytes(a));
    b.extend_from_slice(&rng_state.to_le_bytes());
    hex16(fnv1a64(&b))
}

pub struct Snapshot {
    pub step: u64,
    pub rng_state: u64,
    pub params: Params,
    pub adam: Adam,
    pub perm: Vec<u64>,
}

pub fn save(
    path: &str,
    step: u64,
    rng_state: u64,
    perm: &[u64],
    p: &Params,
    a: &Adam,
) -> Result<(), String> {
    let mut buf = Vec::new();
    buf.extend_from_slice(MAGIC);
    buf.extend_from_slice(&step.to_le_bytes());
    buf.extend_from_slice(&a.t.to_le_bytes());
    buf.extend_from_slice(&rng_state.to_le_bytes());
    append_params(&mut buf, p);
    append_params(&mut buf, &a.m);
    append_params(&mut buf, &a.v);
    for &idx in perm {
        buf.extend_from_slice(&idx.to_le_bytes());
    }
    let ck = fnv1a64(&buf);
    buf.extend_from_slice(&ck.to_le_bytes());
    fs::write(path, &buf).map_err(|e| format!("write {path}: {e}"))
}

struct Cursor<'a> {
    b: &'a [u8],
    pos: usize,
}

impl<'a> Cursor<'a> {
    fn u64(&mut self) -> Result<u64, String> {
        if self.pos + 8 > self.b.len() {
            return Err("snapshot truncated".into());
        }
        let arr: [u8; 8] = self.b[self.pos..self.pos + 8].try_into().unwrap();
        self.pos += 8;
        Ok(u64::from_le_bytes(arr))
    }
    fn f64(&mut self) -> Result<f64, String> {
        Ok(f64::from_bits(self.u64()?))
    }
}

fn read_params(cur: &mut Cursor, d_in: usize, c: usize) -> Result<Params, String> {
    let mut p = Params::zeros(d_in, c);
    for t in p.tensors_mut() {
        for j in 0..t.data.len() {
            t.data[j] = cur.f64()?;
        }
    }
    Ok(p)
}

pub fn load(path: &str, d_in: usize, c: usize, n: usize) -> Result<Snapshot, String> {
    parse(path, d_in, c, n, true)
}

/// Parse a snapshot without verifying the trailing checksum. Used only by the
/// `hash` debugging subcommand so that byte-edited snapshots can be inspected.
pub fn load_lenient(path: &str, d_in: usize, c: usize, n: usize) -> Result<Snapshot, String> {
    parse(path, d_in, c, n, false)
}

fn parse(path: &str, d_in: usize, c: usize, n: usize, verify: bool) -> Result<Snapshot, String> {
    let raw = fs::read(path).map_err(|e| format!("read {path}: {e}"))?;
    if raw.len() < 8 + 8 * 4 {
        return Err("snapshot too small".into());
    }
    if &raw[..8] != MAGIC {
        return Err("bad snapshot magic".into());
    }
    // verify trailing checksum over everything but the last 8 bytes
    let body = &raw[..raw.len() - 8];
    let stored: [u8; 8] = raw[raw.len() - 8..].try_into().unwrap();
    let stored = u64::from_le_bytes(stored);
    if verify && fnv1a64(body) != stored {
        return Err("snapshot checksum mismatch".into());
    }
    let mut cur = Cursor { b: &raw, pos: 8 };
    let step = cur.u64()?;
    let t = cur.u64()?;
    let rng_state = cur.u64()?;
    let params = read_params(&mut cur, d_in, c)?;
    let mut adam = Adam::new(d_in, c);
    adam.m = read_params(&mut cur, d_in, c)?;
    adam.v = read_params(&mut cur, d_in, c)?;
    adam.t = t;
    let mut perm = Vec::with_capacity(n);
    for _ in 0..n {
        perm.push(cur.u64()?);
    }
    // exact length check: cursor + 8-byte checksum must equal file length
    if cur.pos + 8 != raw.len() {
        return Err("snapshot length mismatch".into());
    }
    Ok(Snapshot { step, rng_state, params, adam, perm })
}
EOF_CHECKPOINT_RS

cat > src/dbwriter.rs <<'EOF_DBWRITER_RS'
//! Persist a run into /app/out/runs.db by emitting SQL to the `sqlite3` CLI.
//! Rows for an existing run_id are replaced so re-running a mode is idempotent.

use crate::report::RunReport;
use std::io::Write;
use std::process::{Command, Stdio};

const DDL: &str = "\
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  mode TEXT NOT NULL,
  seed INTEGER NOT NULL,
  resumed_from TEXT,
  FOREIGN KEY(resumed_from) REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS steps (
  run_id TEXT NOT NULL,
  step INTEGER NOT NULL,
  loss REAL NOT NULL,
  grad_norm REAL NOT NULL,
  checkpoint_hash TEXT NOT NULL,
  PRIMARY KEY (run_id, step),
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS checkpoints (
  run_id TEXT NOT NULL,
  step INTEGER NOT NULL,
  weights_hash TEXT NOT NULL,
  optimizer_state_hash TEXT NOT NULL,
  rng_state_hash TEXT NOT NULL,
  PRIMARY KEY (run_id, step),
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
";

fn f64_sql(x: f64) -> String {
    // 17 significant digits round-trips an IEEE double exactly.
    format!("{:.17e}", x)
}

fn build_sql(r: &RunReport) -> String {
    let mut s = String::new();
    s.push_str(DDL);
    s.push_str("BEGIN;\n");
    let id = &r.run_id;
    s.push_str(&format!("DELETE FROM steps WHERE run_id='{id}';\n"));
    s.push_str(&format!("DELETE FROM checkpoints WHERE run_id='{id}';\n"));
    s.push_str(&format!("DELETE FROM runs WHERE run_id='{id}';\n"));
    let resumed = match &r.resumed_from {
        Some(x) => format!("'{x}'"),
        None => "NULL".to_string(),
    };
    s.push_str(&format!(
        "INSERT INTO runs (run_id, mode, seed, resumed_from) VALUES ('{id}','{}',{},{resumed});\n",
        r.mode, r.seed as i64
    ));
    for row in &r.steps {
        s.push_str(&format!(
            "INSERT INTO steps (run_id, step, loss, grad_norm, checkpoint_hash) VALUES ('{id}',{},{},{},'{}');\n",
            row.step, f64_sql(row.loss), f64_sql(row.grad_norm), row.checkpoint_hash
        ));
    }
    for row in &r.checkpoints {
        s.push_str(&format!(
            "INSERT INTO checkpoints (run_id, step, weights_hash, optimizer_state_hash, rng_state_hash) VALUES ('{id}',{},'{}','{}','{}');\n",
            row.step, row.weights_hash, row.optimizer_state_hash, row.rng_state_hash
        ));
    }
    s.push_str("COMMIT;\n");
    s
}

pub fn write_run(db_path: &str, r: &RunReport) -> Result<(), String> {
    let sql = build_sql(r);
    let mut child = Command::new("sqlite3")
        .arg(db_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("spawn sqlite3: {e}"))?;
    child
        .stdin
        .take()
        .ok_or("no stdin for sqlite3")?
        .write_all(sql.as_bytes())
        .map_err(|e| format!("write sql: {e}"))?;
    let out = child.wait_with_output().map_err(|e| format!("wait sqlite3: {e}"))?;
    if !out.status.success() {
        return Err(format!(
            "sqlite3 failed: {}",
            String::from_utf8_lossy(&out.stderr)
        ));
    }
    Ok(())
}
EOF_DBWRITER_RS

cat > src/report.rs <<'EOF_REPORT_RS'
//! Per-step and per-snapshot records collected during a run.

pub struct StepRow {
    pub step: usize,
    pub loss: f64,
    pub grad_norm: f64,
    pub checkpoint_hash: String,
}

pub struct CheckpointRow {
    pub step: usize,
    pub weights_hash: String,
    pub optimizer_state_hash: String,
    pub rng_state_hash: String,
}

pub struct RunReport {
    pub run_id: String,
    pub mode: String,
    pub seed: u64,
    pub resumed_from: Option<String>,
    pub steps: Vec<StepRow>,
    pub checkpoints: Vec<CheckpointRow>,
}

impl RunReport {
    pub fn summarize(&self) {
        let first = self.steps.first();
        let last = self.steps.last();
        eprintln!(
            "[{}] mode={} steps={} first_loss={:.6} last_loss={:.6}",
            self.run_id,
            self.mode,
            self.steps.len(),
            first.map(|r| r.loss).unwrap_or(f64::NAN),
            last.map(|r| r.loss).unwrap_or(f64::NAN),
        );
    }
}
EOF_REPORT_RS

cat > src/main.rs <<'EOF_MAIN_RS'
mod checkpoint;
mod dataset;
mod dbwriter;
mod ops;
mod optimizer;
mod report;
mod rng;
mod tape;
mod tensor;

use optimizer::Adam;
use report::{CheckpointRow, RunReport, StepRow};
use rng::Rng;
use tape::*;
use tensor::Mat;

struct Args {
    mode: String,
    db: String,
    manifest: String,
    inputs: String,
    targets: String,
    seed_file: String,
    resume_file: String,
    snapshot: Option<String>,
    run_id: Option<String>,
    snap_dir: String,
}

fn parse_args() -> Result<Args, String> {
    let mut a = Args {
        mode: String::new(),
        db: "/app/out/runs.db".into(),
        manifest: "/app/data/dataset_manifest.toml".into(),
        inputs: "/app/data/train_inputs.bin".into(),
        targets: "/app/data/train_targets.bin".into(),
        seed_file: "/app/tests_fixtures/golden_seed.toml".into(),
        resume_file: "/app/tests_fixtures/resume_point.toml".into(),
        snapshot: None,
        run_id: None,
        snap_dir: "/app/out/snap".into(),
    };
    let argv: Vec<String> = std::env::args().skip(1).collect();
    let mut i = 0;
    while i < argv.len() {
        let k = &argv[i];
        let mut next = || {
            i += 1;
            argv.get(i).cloned().ok_or_else(|| format!("missing value for {k}"))
        };
        match k.as_str() {
            "--mode" => a.mode = next()?,
            "--db" => a.db = next()?,
            "--manifest" => a.manifest = next()?,
            "--inputs" => a.inputs = next()?,
            "--targets" => a.targets = next()?,
            "--seed-file" => a.seed_file = next()?,
            "--resume-file" => a.resume_file = next()?,
            "--snapshot" => a.snapshot = Some(next()?),
            "--run-id" => a.run_id = Some(next()?),
            "--snap-dir" => a.snap_dir = next()?,
            other => return Err(format!("unknown argument {other}")),
        }
        i += 1;
    }
    if a.mode.is_empty() {
        return Err("--mode is required (nocheckpoint|checkpoint|resume|hash)".into());
    }
    Ok(a)
}

fn gather(x: &Mat, idx: &[usize]) -> Mat {
    let mut out = Mat::zeros(idx.len(), x.cols);
    for (r, &s) in idx.iter().enumerate() {
        for j in 0..x.cols {
            out.set(r, j, x.get(s, j));
        }
    }
    out
}

fn epoch_perm(rng: &mut Rng, n: usize) -> Vec<usize> {
    let mut perm: Vec<usize> = (0..n).collect();
    let mut i = n - 1;
    while i >= 1 {
        let j = rng.below((i + 1) as u64) as usize;
        perm.swap(i, j);
        i -= 1;
    }
    perm
}

fn run_hash(a: &Args) -> Result<(), String> {
    let snap = a.snapshot.as_ref().ok_or("hash mode needs --snapshot")?;
    let manifest = dataset::load_manifest(&a.manifest)?;
    let s = checkpoint::load_lenient(
        snap,
        manifest.input_dim,
        manifest.num_classes,
        manifest.num_samples,
    )?;
    println!("weights_hash={}", checkpoint::weights_hash(&s.params));
    println!("optimizer_state_hash={}", checkpoint::optimizer_hash(&s.adam));
    println!("rng_state_hash={}", checkpoint::rng_hash(s.rng_state));
    println!(
        "full_hash={}",
        checkpoint::full_hash(&s.params, &s.adam, s.rng_state)
    );
    Ok(())
}

fn run_training(a: &Args) -> Result<(), String> {
    let manifest = dataset::load_manifest(&a.manifest)?;
    let seed = dataset::load_seed(&a.seed_file)?;
    let data = dataset::load_data(
        &a.inputs,
        &a.targets,
        manifest.num_samples,
        manifest.input_dim,
    )?;
    let (n, d, c, b) = (
        manifest.num_samples,
        manifest.input_dim,
        manifest.num_classes,
        manifest.batch_size,
    );
    let bpe = (n + b - 1) / b;
    let total = EPOCHS * bpe;

    let remat = a.mode != "nocheckpoint"; // checkpoint & resume rematerialize

    let mut rng;
    let mut params;
    let mut adam;
    let mut step;
    let mut resumed_from = None;
    let mut cur_perm: Vec<usize> = Vec::new();

    if a.mode == "resume" {
        let snap_path = match &a.snapshot {
            Some(p) => p.clone(),
            None => {
                let rs = dataset::load_resume_step(&a.resume_file)?;
                format!("{}/step_{:02}.bin", a.snap_dir, rs)
            }
        };
        let s = checkpoint::load(&snap_path, d, c, n)?;
        rng = Rng::new(0);
        rng.set_state(s.rng_state);
        params = s.params;
        adam = s.adam;
        step = s.step as usize;
        // the snapshot carries the current epoch's permutation; a mid-epoch
        // resume cannot re-derive it from the (already-advanced) rng state.
        cur_perm = s.perm.iter().map(|&x| x as usize).collect();
        resumed_from = Some("checkpoint".to_string());
    } else {
        rng = Rng::new(seed);
        params = Params::init(&mut rng, d, c);
        adam = Adam::new(d, c);
        step = 0;
    }

    if a.mode == "checkpoint" {
        std::fs::create_dir_all(&a.snap_dir).map_err(|e| format!("mkdir snap: {e}"))?;
    }

    let mut steps_rows: Vec<StepRow> = Vec::new();
    let mut ckpt_rows: Vec<CheckpointRow> = Vec::new();

    while step < total {
        let bi = step % bpe;
        if bi == 0 {
            cur_perm = epoch_perm(&mut rng, n);
        }
        let s0 = bi * b;
        let s1 = std::cmp::min(s0 + b, n);
        let idx = &cur_perm[s0..s1];
        let xb = gather(&data.x, idx);
        let yb: Vec<usize> = idx.iter().map(|&s| data.y[s]).collect();

        let t = forward(&params, &xb, &mut rng, remat);
        let (loss, dlogits) = ops::softmax_ce(&t.zo, &yb);
        let mut grads = backward(&params, &t, &dlogits, &mut rng, remat);
        let _pre_clip = clip_layer3(&mut grads);
        let gn = global_norm(&grads);
        adam.step(&mut params, &grads);

        let full = checkpoint::full_hash(&params, &adam, rng.state());
        steps_rows.push(StepRow {
            step,
            loss,
            grad_norm: gn,
            checkpoint_hash: full,
        });

        step += 1;

        if a.mode == "checkpoint" && step < total {
            let path = format!("{}/step_{:02}.bin", a.snap_dir, step);
            let perm_u64: Vec<u64> = cur_perm.iter().map(|&x| x as u64).collect();
            checkpoint::save(&path, step as u64, rng.state(), &perm_u64, &params, &adam)?;
            ckpt_rows.push(CheckpointRow {
                step,
                weights_hash: checkpoint::weights_hash(&params),
                optimizer_state_hash: checkpoint::optimizer_hash(&adam),
                rng_state_hash: checkpoint::rng_hash(rng.state()),
            });
        }
    }

    let run_id = a
        .run_id
        .clone()
        .unwrap_or_else(|| a.mode.clone());
    let report = RunReport {
        run_id,
        mode: a.mode.clone(),
        seed,
        resumed_from,
        steps: steps_rows,
        checkpoints: ckpt_rows,
    };
    if let Some(parent) = std::path::Path::new(&a.db).parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("mkdir out: {e}"))?;
    }
    dbwriter::write_run(&a.db, &report)?;
    report.summarize();
    Ok(())
}

fn main() {
    let args = match parse_args() {
        Ok(a) => a,
        Err(e) => {
            eprintln!("error: {e}");
            std::process::exit(2);
        }
    };
    let r = match args.mode.as_str() {
        "nocheckpoint" | "checkpoint" | "resume" => run_training(&args),
        "hash" => run_hash(&args),
        other => Err(format!("unknown mode {other}")),
    };
    if let Err(e) = r {
        eprintln!("error: {e}");
        std::process::exit(1);
    }
}
EOF_MAIN_RS


cargo build --release --offline

BIN=target/release/engine
"$BIN" --mode nocheckpoint
"$BIN" --mode checkpoint
"$BIN" --mode resume

echo "solve.sh complete: $(sqlite3 out/runs.db 'SELECT run_id, COUNT(*) FROM steps GROUP BY run_id;')"
