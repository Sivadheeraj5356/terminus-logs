use crate::types::Model;

pub fn correlation_matrix(model_a: &Model, model_b: &Model, layer_idx: usize) -> Vec<Vec<f64>> {
    let wa = &model_a.layers[layer_idx].w;
    let wb = &model_b.layers[layer_idx].w;
    let d = wa.len();
    let mut c = vec![vec![0.0; d]; d];
    for i in 0..d {
        for j in 0..d {
            let dot: f64 = wa[i].iter().zip(wb[j].iter()).map(|(a, b)| a * b).sum();
            c[i][j] = dot;
        }
    }
    c
}

pub fn activation_correlation(_acts_a: &[Vec<f64>], _acts_b: &[Vec<f64>]) -> Vec<Vec<f64>> {
    vec![]
}

pub fn pearson(_a: &[f64], _b: &[f64]) -> f64 {
    0.0
}
