#!/usr/bin/env bash
printf '%s' 'use std::env;
use std::fs;

fn gray(i: usize) -> usize {
    i ^ (i >> 1)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let spec_path = &args[1];
    let out_path = &args[2];
    let text = fs::read_to_string(spec_path).unwrap();
    let mut lines = text.lines();
    let n: usize = lines.next().unwrap().trim().parse().unwrap();
    let big: usize = 1usize << n;
    let mut amps: Vec<f64> = Vec::with_capacity(big);
    for _ in 0..big {
        let v: f64 = lines.next().unwrap().trim().parse().unwrap();
        amps.push(v);
    }

    let mut s = String::new();
    s.push_str("OPENQASM 3;\n");
    s.push_str("include \"stdgates.inc\";\n");
    s.push_str(&format!("qubit[{}] q;\n", n));

    for k in 0..n {
        let block: usize = 1usize << (n - k);
        let half: usize = block / 2;
        let num_prefix: usize = 1usize << k;
        let mut alpha: Vec<f64> = Vec::with_capacity(num_prefix);
        for p in 0..num_prefix {
            let base = p * block;
            let mut left = 0.0f64;
            let mut right = 0.0f64;
            for i in 0..half {
                let l = amps[base + i];
                left += l * l;
            }
            for i in half..block {
                let r = amps[base + i];
                right += r * r;
            }
            if left <= 0.0 && right <= 0.0 {
                alpha.push(0.0);
            } else {
                alpha.push(2.0 * (right.sqrt()).atan2(left.sqrt()));
            }
        }

        if k == 0 {
            s.push_str(&format!("ry({}) q[{}];\n", fmt(alpha[0]), k));
            continue;
        }

        let m = num_prefix;
        let mut theta = vec![0.0f64; m];
        for i in 0..m {
            let gi = gray(i);
            let mut acc = 0.0f64;
            for j in 0..m {
                let b = (gi & j).count_ones();
                let sign = if b % 2 == 0 { 1.0 } else { -1.0 };
                acc += sign * alpha[j];
            }
            theta[i] = acc / (m as f64);
        }
        for i in 0..m {
            s.push_str(&format!("ry({}) q[{}];\n", fmt(theta[i]), k));
            let ctrl_bit: usize = if i == m - 1 {
                k - 1
            } else {
                let diff = gray(i) ^ gray(i + 1);
                trailing_bit(diff)
            };
            let ctrl_qubit = k - 1 - ctrl_bit;
            s.push_str(&format!("cx q[{}], q[{}];\n", ctrl_qubit, k));
        }
    }

    fs::write(out_path, s).unwrap();
}

fn trailing_bit(x: usize) -> usize {
    let mut v = x;
    let mut i = 0usize;
    while v & 1 == 0 {
        v >>= 1;
        i += 1;
    }
    i
}

fn fmt(x: f64) -> String {
    format!("{:.17e}", x)
}
' > /app/submission.rs
