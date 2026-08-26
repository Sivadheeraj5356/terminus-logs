#!/bin/bash
set -eu
cd /app

cat > solver.rs <<'RUST'
use std::cmp::Ordering;
use std::env;
use std::fs;

#[derive(Clone, PartialEq, Eq)]
pub struct Big {
    pub neg: bool,
    pub mag: Vec<u32>,
}

fn trim(mut v: Vec<u32>) -> Vec<u32> {
    while let Some(&0) = v.last() {
        v.pop();
    }
    v
}

fn cmp_mag(a: &[u32], b: &[u32]) -> Ordering {
    if a.len() != b.len() {
        return a.len().cmp(&b.len());
    }
    for i in (0..a.len()).rev() {
        if a[i] != b[i] {
            return a[i].cmp(&b[i]);
        }
    }
    Ordering::Equal
}

fn add_mag(a: &[u32], b: &[u32]) -> Vec<u32> {
    let mut r = Vec::new();
    let mut carry = 0u64;
    let n = a.len().max(b.len());
    for i in 0..n {
        let x = *a.get(i).unwrap_or(&0) as u64;
        let y = *b.get(i).unwrap_or(&0) as u64;
        let s = x + y + carry;
        r.push((s & 0xffff_ffff) as u32);
        carry = s >> 32;
    }
    if carry != 0 {
        r.push(carry as u32);
    }
    trim(r)
}

fn sub_mag(a: &[u32], b: &[u32]) -> Vec<u32> {
    let mut r = Vec::new();
    let mut borrow = 0i64;
    for i in 0..a.len() {
        let x = a[i] as i64;
        let y = *b.get(i).unwrap_or(&0) as i64;
        let mut d = x - y - borrow;
        if d < 0 {
            d += 1i64 << 32;
            borrow = 1;
        } else {
            borrow = 0;
        }
        r.push(d as u32);
    }
    trim(r)
}

fn mul_mag(a: &[u32], b: &[u32]) -> Vec<u32> {
    if a.is_empty() || b.is_empty() {
        return Vec::new();
    }
    let mut r = vec![0u32; a.len() + b.len()];
    for i in 0..a.len() {
        let mut carry = 0u64;
        let ai = a[i] as u64;
        for j in 0..b.len() {
            let cur = r[i + j] as u64 + ai * (b[j] as u64) + carry;
            r[i + j] = (cur & 0xffff_ffff) as u32;
            carry = cur >> 32;
        }
        let mut k = i + b.len();
        while carry != 0 {
            let cur = r[k] as u64 + carry;
            r[k] = (cur & 0xffff_ffff) as u32;
            carry = cur >> 32;
            k += 1;
        }
    }
    trim(r)
}

fn shl1(v: &[u32]) -> Vec<u32> {
    let mut r = Vec::with_capacity(v.len() + 1);
    let mut carry = 0u32;
    for &limb in v {
        let nc = limb >> 31;
        r.push((limb << 1) | carry);
        carry = nc;
    }
    if carry != 0 {
        r.push(carry);
    }
    trim(r)
}

fn shr1(v: &[u32]) -> Vec<u32> {
    let mut r = vec![0u32; v.len()];
    for i in (0..v.len()).rev() {
        let hi = if i + 1 < v.len() { v[i + 1] & 1 } else { 0 };
        r[i] = (v[i] >> 1) | (hi << 31);
    }
    trim(r)
}

fn is_even(v: &[u32]) -> bool {
    v.is_empty() || v[0] & 1 == 0
}

fn gcd_mag(mut a: Vec<u32>, mut b: Vec<u32>) -> Vec<u32> {
    if a.is_empty() {
        return b;
    }
    if b.is_empty() {
        return a;
    }
    let mut shift = 0;
    while is_even(&a) && is_even(&b) {
        a = shr1(&a);
        b = shr1(&b);
        shift += 1;
    }
    while is_even(&a) {
        a = shr1(&a);
    }
    loop {
        while is_even(&b) {
            b = shr1(&b);
        }
        if cmp_mag(&a, &b) == Ordering::Greater {
            std::mem::swap(&mut a, &mut b);
        }
        b = sub_mag(&b, &a);
        if b.is_empty() {
            break;
        }
    }
    for _ in 0..shift {
        a = shl1(&a);
    }
    a
}

fn bit(v: &[u32], i: usize) -> u32 {
    let limb = i / 32;
    if limb >= v.len() {
        return 0;
    }
    (v[limb] >> (i % 32)) & 1
}

fn divmod_mag(a: &[u32], b: &[u32]) -> (Vec<u32>, Vec<u32>) {
    let mut q: Vec<u32> = Vec::new();
    let mut r: Vec<u32> = Vec::new();
    let total = a.len() * 32;
    for idx in (0..total).rev() {
        r = shl1(&r);
        if bit(a, idx) == 1 {
            if r.is_empty() {
                r.push(1);
            } else {
                r[0] |= 1;
            }
        }
        if cmp_mag(&r, b) != Ordering::Less {
            r = sub_mag(&r, b);
            let limb = idx / 32;
            while q.len() <= limb {
                q.push(0);
            }
            q[limb] |= 1u32 << (idx % 32);
        }
    }
    (trim(q), trim(r))
}

impl Big {
    pub fn zero() -> Big {
        Big { neg: false, mag: Vec::new() }
    }

    fn make(neg: bool, mag: Vec<u32>) -> Big {
        let m = trim(mag);
        Big { neg: neg && !m.is_empty(), mag: m }
    }

    pub fn from_i64(v: i64) -> Big {
        let neg = v < 0;
        let mut u = (v as i128).unsigned_abs();
        let mut mag = Vec::new();
        while u != 0 {
            mag.push((u & 0xffff_ffff) as u32);
            u >>= 32;
        }
        Big::make(neg, mag)
    }

    pub fn from_dec(s: &str) -> Big {
        let s = s.trim();
        let (neg, digits) = if let Some(rest) = s.strip_prefix('-') {
            (true, rest)
        } else if let Some(rest) = s.strip_prefix('+') {
            (false, rest)
        } else {
            (false, s)
        };
        let mut acc = Big::zero();
        let ten = Big::from_i64(10);
        for ch in digits.bytes() {
            let d = Big::from_i64((ch - b'0') as i64);
            acc = acc.mul(&ten).add(&d);
        }
        Big::make(neg, acc.mag)
    }

    pub fn is_zero(&self) -> bool {
        self.mag.is_empty()
    }

    pub fn sign(&self) -> i32 {
        if self.mag.is_empty() {
            0
        } else if self.neg {
            -1
        } else {
            1
        }
    }

    pub fn cmp(&self, o: &Big) -> Ordering {
        match (self.neg, o.neg) {
            (false, true) => Ordering::Greater,
            (true, false) => Ordering::Less,
            (false, false) => cmp_mag(&self.mag, &o.mag),
            (true, true) => cmp_mag(&o.mag, &self.mag),
        }
    }

    pub fn neg(&self) -> Big {
        Big::make(!self.neg, self.mag.clone())
    }

    pub fn add(&self, o: &Big) -> Big {
        if self.neg == o.neg {
            Big::make(self.neg, add_mag(&self.mag, &o.mag))
        } else {
            match cmp_mag(&self.mag, &o.mag) {
                Ordering::Equal => Big::zero(),
                Ordering::Greater => Big::make(self.neg, sub_mag(&self.mag, &o.mag)),
                Ordering::Less => Big::make(o.neg, sub_mag(&o.mag, &self.mag)),
            }
        }
    }

    pub fn sub(&self, o: &Big) -> Big {
        self.add(&o.neg())
    }

    pub fn mul(&self, o: &Big) -> Big {
        Big::make(self.neg != o.neg, mul_mag(&self.mag, &o.mag))
    }

    pub fn divmod(&self, o: &Big) -> (Big, Big) {
        let (q, r) = divmod_mag(&self.mag, &o.mag);
        (Big::make(self.neg != o.neg, q), Big::make(self.neg, r))
    }

    pub fn gcd(&self, o: &Big) -> Big {
        Big::make(false, gcd_mag(self.mag.clone(), o.mag.clone()))
    }

    pub fn to_dec(&self) -> String {
        if self.is_zero() {
            return String::from("0");
        }
        let mut m = self.mag.clone();
        let base = 1_000_000_000u64;
        let mut chunks: Vec<u32> = Vec::new();
        while !m.is_empty() {
            let mut rem = 0u64;
            for i in (0..m.len()).rev() {
                let cur = (rem << 32) | m[i] as u64;
                m[i] = (cur / base) as u32;
                rem = cur % base;
            }
            m = trim(m);
            chunks.push(rem as u32);
        }
        let mut out = String::new();
        if self.neg {
            out.push('-');
        }
        out.push_str(&chunks[chunks.len() - 1].to_string());
        for i in (0..chunks.len() - 1).rev() {
            out.push_str(&format!("{:09}", chunks[i]));
        }
        out
    }
}

#[derive(Clone)]
pub struct Rat {
    pub num: Big,
    pub den: Big,
}

impl Rat {
    pub fn new(num: Big, den: Big) -> Rat {
        let mut n = num;
        let mut d = den;
        if d.sign() < 0 {
            n = n.neg();
            d = d.neg();
        }
        if n.is_zero() {
            return Rat { num: Big::zero(), den: Big::from_i64(1) };
        }
        let g = n.gcd(&d);
        if !g.is_zero() && g.cmp(&Big::from_i64(1)) != Ordering::Equal {
            n = n.divmod(&g).0;
            d = d.divmod(&g).0;
        }
        Rat { num: n, den: d }
    }

    pub fn from_big(v: Big) -> Rat {
        Rat { num: v, den: Big::from_i64(1) }
    }

    pub fn from_i64(v: i64) -> Rat {
        Rat { num: Big::from_i64(v), den: Big::from_i64(1) }
    }

    pub fn is_zero(&self) -> bool {
        self.num.is_zero()
    }

    pub fn add(&self, o: &Rat) -> Rat {
        Rat::new(self.num.mul(&o.den).add(&o.num.mul(&self.den)), self.den.mul(&o.den))
    }

    pub fn sub(&self, o: &Rat) -> Rat {
        Rat::new(self.num.mul(&o.den).sub(&o.num.mul(&self.den)), self.den.mul(&o.den))
    }

    pub fn mul(&self, o: &Rat) -> Rat {
        Rat::new(self.num.mul(&o.num), self.den.mul(&o.den))
    }

    pub fn div(&self, o: &Rat) -> Rat {
        Rat::new(self.num.mul(&o.den), self.den.mul(&o.num))
    }

    pub fn to_pair(&self) -> String {
        format!("{}/{}", self.num.to_dec(), self.den.to_dec())
    }
}

pub struct Cond {
    pub x: Big,
    pub j: usize,
    pub v: Big,
}

fn falling(k: usize, j: usize) -> Big {
    // k! / (k-j)! = k (k-1) ... (k-j+1)
    let mut r = Big::from_i64(1);
    for t in 0..j {
        r = r.mul(&Big::from_i64((k - t) as i64));
    }
    r
}

fn pow(x: &Big, e: usize) -> Big {
    let mut r = Big::from_i64(1);
    let mut base = x.clone();
    let mut n = e;
    while n > 0 {
        if n & 1 == 1 {
            r = r.mul(&base);
        }
        base = base.mul(&base);
        n >>= 1;
    }
    r
}

fn row_of(x: &Big, j: usize, n: usize) -> Vec<Rat> {
    (0..n)
        .map(|k| {
            if k >= j {
                Rat::from_big(falling(k, j).mul(&pow(x, k - j)))
            } else {
                Rat::from_i64(0)
            }
        })
        .collect()
}

pub enum Verdict {
    // exactly one polynomial fits: its coefficient vector
    Unique(Vec<Rat>),
    // no polynomial fits: multipliers over the conditions whose weighted row
    // combination is the zero functional while the weighted values are nonzero
    None(Vec<Rat>),
    // more than one fits: two distinct coefficient vectors, each a solution
    Many(Vec<Rat>, Vec<Rat>),
}

pub fn classify(n: usize, conds: &[Cond]) -> Verdict {
    let m = conds.len();
    // work on [ A (n) | b (1) | I_m (m) ] so the row operations that expose an
    // inconsistent row also yield the multipliers that certify it
    let w = n + 1 + m;
    let mut aug: Vec<Vec<Rat>> = Vec::with_capacity(m);
    for (i, c) in conds.iter().enumerate() {
        let mut row = row_of(&c.x, c.j, n);
        row.push(Rat::from_big(c.v.clone()));
        for t in 0..m {
            row.push(Rat::from_i64(if t == i { 1 } else { 0 }));
        }
        aug.push(row);
    }
    let mut pivots: Vec<usize> = Vec::new();
    let mut r = 0usize;
    for col in 0..n {
        let piv = (r..m).find(|&i| !aug[i][col].is_zero());
        let piv = match piv {
            Some(p) => p,
            None => continue,
        };
        aug.swap(r, piv);
        let inv = aug[r][col].clone();
        for t in 0..w {
            aug[r][t] = aug[r][t].div(&inv);
        }
        for i in 0..m {
            if i != r && !aug[i][col].is_zero() {
                let f = aug[i][col].clone();
                for t in 0..w {
                    let sub = f.mul(&aug[r][t]);
                    aug[i][t] = aug[i][t].sub(&sub);
                }
            }
        }
        pivots.push(col);
        r += 1;
        if r == m {
            break;
        }
    }
    // inconsistency: a row with all-zero coefficients but nonzero value; the
    // trailing m entries of that row are the certificate multipliers
    for i in 0..m {
        let zero_coeffs = (0..n).all(|t| aug[i][t].is_zero());
        if zero_coeffs && !aug[i][n].is_zero() {
            let lam: Vec<Rat> = (0..m).map(|t| aug[i][n + 1 + t].clone()).collect();
            return Verdict::None(lam);
        }
    }
    let rank = pivots.len();
    if rank == n {
        let mut coeffs = vec![Rat::from_i64(0); n];
        for (i, &col) in pivots.iter().enumerate() {
            coeffs[col] = aug[i][n].clone();
        }
        return Verdict::Unique(coeffs);
    }
    // consistent but rank deficient: a particular solution and one null direction
    let mut particular = vec![Rat::from_i64(0); n];
    for (i, &col) in pivots.iter().enumerate() {
        particular[col] = aug[i][n].clone();
    }
    let free = (0..n).find(|c| !pivots.contains(c)).unwrap();
    let mut null = vec![Rat::from_i64(0); n];
    null[free] = Rat::from_i64(1);
    for (i, &col) in pivots.iter().enumerate() {
        null[col] = Rat::from_i64(0).sub(&aug[i][free]);
    }
    let other: Vec<Rat> = (0..n).map(|k| particular[k].add(&null[k])).collect();
    Verdict::Many(particular, other)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let text = fs::read_to_string(&args[1]).unwrap();
    let mut toks = text.split_whitespace();
    let t: usize = toks.next().unwrap().parse().unwrap();
    let mut out = String::new();
    for _ in 0..t {
        let n: usize = toks.next().unwrap().parse().unwrap();
        let c: usize = toks.next().unwrap().parse().unwrap();
        let mut conds = Vec::with_capacity(c);
        for _ in 0..c {
            let x = Big::from_dec(toks.next().unwrap());
            let j: usize = toks.next().unwrap().parse().unwrap();
            let v = Big::from_dec(toks.next().unwrap());
            conds.push(Cond { x, j, v });
        }
        let line = |v: &[Rat]| v.iter().map(|r| r.to_pair()).collect::<Vec<_>>().join(" ");
        match classify(n, &conds) {
            Verdict::Unique(coeffs) => {
                out.push_str(&n.to_string());
                out.push('\n');
                out.push_str(&line(&coeffs));
                out.push('\n');
            }
            Verdict::None(lam) => {
                out.push_str("NONE\n");
                out.push_str(&line(&lam));
                out.push('\n');
            }
            Verdict::Many(a, b) => {
                out.push_str("MANY\n");
                out.push_str(&line(&a));
                out.push('\n');
                out.push_str(&line(&b));
                out.push('\n');
            }
        }
    }
    print!("{}", out);
}
RUST

export PATH="/usr/local/cargo/bin:$PATH"
make run
echo "solved"
