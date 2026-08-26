use std::env;
use std::fs;
use std::io::{self, Write};

const D: usize = 4;

fn read_rows(path: &str, with_label: bool) -> (Vec<[i64; D]>, Vec<i64>) {
    let s = fs::read_to_string(path).unwrap();
    let mut xs = Vec::new();
    let mut ys = Vec::new();
    for line in s.lines().skip(1) {
        let l = line.trim_end_matches('\r');
        if l.is_empty() {
            continue;
        }
        let f: Vec<&str> = l.split(',').collect();
        let mut x = [0i64; D];
        for j in 0..D {
            x[j] = f[1 + j].parse().unwrap();
        }
        xs.push(x);
        if with_label {
            ys.push(f[1 + D].parse().unwrap());
        }
    }
    (xs, ys)
}

fn labels(j: usize, t: usize, cap: i64, delay: usize, xs: &[[i64; D]]) -> Vec<i64> {
    let n = xs.len();
    let mut snap = vec![0i64; n];
    let mut acc = 0i64;
    for i in 0..n {
        snap[i] = acc;
        acc += xs[i][t];
        if acc >= cap {
            acc = 0;
        }
    }
    let mut out = Vec::with_capacity(n);
    for i in 0..n {
        let bar = if i >= delay { snap[i - delay] } else { 0 };
        out.push(if xs[i][j] > bar { 1 } else { 0 });
    }
    out
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let dir = &args[1];
    let (trx, tr_y) = read_rows(&format!("{}/train.csv", dir), true);
    let (tex, _) = read_rows(&format!("{}/test.csv", dir), false);

    // Infer the hidden parameters: the (primary feature, trigger feature, reset cap, delay) whose
    // self-resetting accumulator rule reproduces every training label. The contract guarantees such
    // parameters also reproduce the held-out test labels.
    let mut best: Option<(usize, usize, i64, usize)> = None;
    's: for j in 0..D {
        for t in 0..D {
            if t == j {
                continue;
            }
            for cap in 2..=20i64 {
                for delay in 0..=5usize {
                    if labels(j, t, cap, delay, &trx) == tr_y {
                        best = Some((j, t, cap, delay));
                        break 's;
                    }
                }
            }
        }
    }
    let (j, t, cap, delay) = best.unwrap_or((0, 1, 10, 1));
    let pred = labels(j, t, cap, delay, &tex);

    let mut out = String::from("{\"predictions\":[");
    for (i, p) in pred.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&p.to_string());
    }
    out.push_str("]}");
    io::stdout().write_all(out.as_bytes()).unwrap();
}
