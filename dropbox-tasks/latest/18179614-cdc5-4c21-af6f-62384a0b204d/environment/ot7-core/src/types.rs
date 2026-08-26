use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct AnnealSpec {
    pub start_epsilon: f64,
    pub factor: f64,
    pub stages: usize,
}

#[derive(Debug, Deserialize)]
pub struct Request {
    pub cost: Vec<Vec<f64>>,
    pub supply: Vec<f64>,
    pub demand: Vec<f64>,
    pub epsilon: f64,
    pub max_iters: usize,
    pub tol: f64,
    pub anneal: Option<AnnealSpec>,
    pub warm_f: Option<Vec<f64>>,
    pub warm_g: Option<Vec<f64>>,
}

#[derive(Debug, Serialize)]
pub struct Response {
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    pub accepted: bool,
    pub plan: Vec<Vec<f64>>,
    pub wasserstein: f64,
    pub f: Vec<f64>,
    pub g: Vec<f64>,
    pub iters: usize,
}
