use crate::types::Output;

pub fn calculate_mean(outputs: &[Output]) -> f64 {
    if outputs.is_empty() {
        return 0.0;
    }
    let sum: f64 = outputs.iter().map(|o| o.value).sum();
    sum / outputs.len() as f64
}
