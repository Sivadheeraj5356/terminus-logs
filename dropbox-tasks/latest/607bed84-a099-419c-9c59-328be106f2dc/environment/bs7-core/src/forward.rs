use crate::types::{Layer, Model};

fn relu(x: f64) -> f64 {
    if x > 0.0 { x } else { 0.0 }
}

fn matvec(w: &[Vec<f64>], x: &[f64]) -> Vec<f64> {
    w.iter()
        .map(|row| row.iter().zip(x.iter()).map(|(a, b)| a * b).sum())
        .collect()
}

pub fn forward(model: &Model, x: &[f64]) -> Vec<f64> {
    let mut h = x.to_vec();
    let last = model.layers.len() - 1;
    for (i, layer) in model.layers.iter().enumerate() {
        let mut out = matvec(&layer.w, &h);
        for (o, b) in out.iter_mut().zip(layer.b.iter()) {
            *o += b;
        }
        if i < last {
            h = out.into_iter().map(relu).collect();
        } else {
            h = out;
        }
    }
    h
}

pub fn hidden_activations(model: &Model, samples: &[Vec<f64>], layer_idx: usize) -> Vec<Vec<f64>> {
    let mut out = Vec::new();
    for x in samples {
        let mut h = x.clone();
        for i in 0..=layer_idx {
            let layer = &model.layers[i];
            let mut act = matvec(&layer.w, &h);
            for (o, b) in act.iter_mut().zip(layer.b.iter()) {
                *o += b;
            }
            if i < layer_idx {
                h = act.into_iter().map(relu).collect();
            } else {
                h = act.into_iter().map(relu).collect();
            }
        }
        out.push(h);
    }
    out
}

pub fn mse(model: &Model, reference: &Model, samples: &[Vec<f64>]) -> f64 {
    let mut err = 0.0;
    for x in samples {
        let ya = forward(reference, x);
        let yb = forward(model, x);
        let n = ya.len() as f64;
        err += ya.iter().zip(yb.iter()).map(|(a, b)| (a - b).powi(2)).sum::<f64>() / n;
    }
    err / samples.len() as f64
}

pub fn average_models(a: &Model, b: &Model, weight: f64) -> Model {
    let layers = a
        .layers
        .iter()
        .zip(b.layers.iter())
        .map(|(la, lb)| Layer {
            w: la
                .w
                .iter()
                .zip(lb.w.iter())
                .map(|(ra, rb)| {
                    ra.iter()
                        .zip(rb.iter())
                        .map(|(x, y)| weight * x + (1.0 - weight) * y)
                        .collect()
                })
                .collect(),
            b: la
                .b
                .iter()
                .zip(lb.b.iter())
                .map(|(x, y)| weight * x + (1.0 - weight) * y)
                .collect(),
        })
        .collect();
    Model { layers }
}
