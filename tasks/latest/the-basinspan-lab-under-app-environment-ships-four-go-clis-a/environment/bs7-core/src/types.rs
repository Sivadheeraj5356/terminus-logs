use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Layer {
    #[serde(rename = "W")]
    pub w: Vec<Vec<f64>>,
    pub b: Vec<f64>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Model {
    pub layers: Vec<Layer>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Arch {
    pub input_dim: usize,
    pub hidden_dims: Vec<usize>,
    pub output_dim: usize,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SolveIn {
    pub arch: Arch,
    pub align_samples: Vec<Vec<f64>>,
    pub eval_samples: Vec<Vec<f64>>,
    pub model_a: Model,
    pub model_b: Model,
    pub merge_weight: f64,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct TraceRow {
    pub layer: usize,
    pub neuron_a: usize,
    pub neuron_b: usize,
    pub correlation: f64,
    pub assignment_cost: f64,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SolveOut {
    pub ok: bool,
    pub align_cost: f64,
    pub eval_mse: f64,
    pub naive_mse: f64,
    pub barrier_value: f64,
    pub permutations: Vec<Vec<usize>>,
    pub trace: Vec<TraceRow>,
    pub merge_digest_hex: String,
}
