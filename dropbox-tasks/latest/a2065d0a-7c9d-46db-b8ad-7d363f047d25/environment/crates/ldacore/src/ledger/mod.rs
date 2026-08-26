pub fn add(
    n_dk: &mut [Vec<u64>],
    n_kw: &mut [Vec<u64>],
    n_k: &mut [u64],
    d: usize,
    topic: usize,
    w: usize,
) {
    n_dk[d][topic] += 1;
    n_kw[topic][w] += 1;
    n_k[topic] += 1;
}

pub fn remove(
    n_dk: &mut [Vec<u64>],
    n_kw: &mut [Vec<u64>],
    n_k: &mut [u64],
    d: usize,
    topic: usize,
    w: usize,
) {
    let _ = n_k;
    n_dk[d][topic] -= 1;
    n_kw[topic][w] -= 1;
}
