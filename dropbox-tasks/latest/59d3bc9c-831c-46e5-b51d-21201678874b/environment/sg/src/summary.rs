pub fn norm_summary(values: &[f64]) -> f64 {
    values.iter().map(|v| v.abs()).sum()
}
