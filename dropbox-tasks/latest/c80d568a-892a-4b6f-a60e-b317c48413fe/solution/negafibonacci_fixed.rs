//! Negafibonacci coding — oracle implementation.
//!
//! Crate convention: `F_2 = 1, F_3 = 2, F_4 = 3, F_5 = 5, …` (no F_0
//! or F_1). Negafibonacci indices are u32 `k ≥ 1` with the standard
//! identity `F_{-k} = (-1)^{k+1} · |F_k|`, where `|F_1| = 1` is a
//! special-cased boundary value (equal to `fibonacci(2)` under the
//! crate convention). All k ≥ 2 delegate to `crate::fibonacci`.
//!
//! Identity: `F_{-k} + F_{-(k+1)} = F_{-(k-1)}` for k ≥ 2; for k = 1
//! the collapse is `F_{-1} + F_{-2} = 0`, so adjacent indices [1, 2]
//! drop entirely.

use crate::fibonacci::fibonacci;

pub fn negafib_abs(k: u32) -> i64 {
    debug_assert!(k >= 1);
    if k == 1 { 1 } else { fibonacci(k) as i64 }
}

pub fn negafib_value(k: u32) -> i64 {
    let abs = negafib_abs(k);
    if k % 2 == 0 { -abs } else { abs }
}

fn find_smallest_k_covering(n: i64) -> u32 {
    let mut k: u32 = 1;
    loop {
        let v = negafib_value(k);
        if v.signum() == n.signum() && v.abs() >= n.abs() {
            return k;
        }
        k += 1;
        if k > 90 {
            panic!("negafib: cannot cover n");
        }
    }
}

fn normalize(mut indices: Vec<u32>) -> Vec<u32> {
    loop {
        indices.sort();
        indices.dedup();
        let mut i = 0;
        let mut hit = false;
        let mut next: Vec<u32> = Vec::new();
        while i < indices.len() {
            if i + 1 < indices.len() && indices[i + 1] == indices[i] + 1 {
                if indices[i] >= 2 {
                    next.push(indices[i] - 1);
                }
                i += 2;
                hit = true;
            } else {
                next.push(indices[i]);
                i += 1;
            }
        }
        indices = next;
        if !hit {
            return indices;
        }
    }
}

pub fn negafib_indices(mut n: i64) -> Vec<u32> {
    let mut out: Vec<u32> = Vec::new();
    while n != 0 {
        let k = find_smallest_k_covering(n);
        out.push(k);
        n -= negafib_value(k);
    }
    normalize(out)
}

pub fn negafib_sum(indices: &[u32]) -> i64 {
    indices.iter().map(|&k| negafib_value(k)).sum()
}

pub fn negafib_is_minimal(indices: &[u32]) -> bool {
    for i in 1..indices.len() {
        if indices[i] <= indices[i - 1] {
            return false;
        }
        if indices[i] == indices[i - 1] + 1 {
            return false;
        }
    }
    true
}
