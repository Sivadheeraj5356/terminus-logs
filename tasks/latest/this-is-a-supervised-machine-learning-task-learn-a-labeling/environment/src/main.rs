// Starter scaffold. The input/output plumbing is done for you; the rule-learning is not.
//
// This reads the labeled train.csv and the unlabeled test.csv from the data directory given as the
// first argument and prints {"predictions":[...]} with one 0/1 label per test row, in order. As
// shipped it predicts all zeros, which will NOT pass. Replace `infer_and_predict` with a solver
// that infers the hidden labeling rule from the training rows and applies it to the test rows.
// See docs/contract.md for the data format, what is guaranteed about the rule, and the grading.

use std::env;
use std::fs;

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

fn infer_and_predict(_trx: &[[i64; D]], _tr_y: &[i64], tex: &[[i64; D]]) -> Vec<i64> {
    // TODO: infer the hidden rule from (_trx, _tr_y) and predict a label for each row of `tex`.
    // The placeholder below predicts all zeros and will not clear the accuracy bar.
    vec![0; tex.len()]
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let dir = &args[1];
    let (trx, tr_y) = read_rows(&format!("{}/train.csv", dir), true);
    let (tex, _) = read_rows(&format!("{}/test.csv", dir), false);

    let pred = infer_and_predict(&trx, &tr_y, &tex);

    let mut out = String::from("{\"predictions\":[");
    for (i, p) in pred.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&p.to_string());
    }
    out.push_str("]}");
    println!("{}", out);
}
