use crate::types::{Layer, Model};

pub fn hungarian(cost: &[Vec<f64>]) -> Vec<usize> {
    let n = cost.len();
    let mut u = vec![0.0; n + 1];
    let mut v = vec![0.0; n + 1];
    let mut p = vec![0usize; n + 1];
    let mut way = vec![0usize; n + 1];
    for i in 1..=n {
        p[0] = i;
        let mut j0 = 0usize;
        let mut minv = vec![f64::INFINITY; n + 1];
        let mut used = vec![false; n + 1];
        loop {
            used[j0] = true;
            let i0 = p[j0];
            let mut delta = f64::INFINITY;
            let mut j1 = 0usize;
            for j in 1..=n {
                if used[j] {
                    continue;
                }
                let cur = cost[i0 - 1][j - 1] - u[i0] - v[j];
                if cur < minv[j] {
                    minv[j] = cur;
                    way[j] = j0;
                }
                if minv[j] < delta {
                    delta = minv[j];
                    j1 = j;
                }
            }
            for j in 0..=n {
                if used[j] {
                    u[p[j]] += delta;
                    v[j] -= delta;
                } else {
                    minv[j] -= delta;
                }
            }
            j0 = j1;
            if p[j0] == 0 {
                break;
            }
        }
        loop {
            let j1 = way[j0];
            p[j0] = p[j1];
            j0 = j1;
            if j0 == 0 {
                break;
            }
        }
    }
    let mut assign = vec![0usize; n];
    for j in 1..=n {
        assign[p[j] - 1] = j - 1;
    }
    assign
}

fn permute_rows(layer: &Layer, perm: &[usize]) -> Layer {
    let w = (0..perm.len()).map(|i| layer.w[perm[i]].clone()).collect();
    let b = (0..perm.len()).map(|i| layer.b[perm[i]]).collect();
    Layer { w, b }
}

pub fn align_model_b(model_b: &Model, perms: &[Vec<usize>]) -> Model {
    let mut layers = model_b.layers.clone();
    for (li, perm) in perms.iter().enumerate() {
        layers[li] = permute_rows(&layers[li], perm);
    }
    Model { layers }
}

pub fn permute_cols(_w: &[Vec<f64>], _perm: &[usize]) -> Vec<Vec<f64>> {
    vec![]
}
