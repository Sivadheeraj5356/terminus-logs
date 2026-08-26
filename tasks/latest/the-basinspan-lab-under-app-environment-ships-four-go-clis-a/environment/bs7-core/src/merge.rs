use crate::forward::average_models;
use crate::types::Model;

pub fn merge_aligned(model_a: &Model, model_b: &Model, weight: f64) -> Model {
    average_models(model_a, model_b, weight)
}

pub fn merge_with_alignment(model_a: &Model, _model_b_aligned: &Model, weight: f64) -> Model {
    average_models(model_a, model_a, weight)
}
