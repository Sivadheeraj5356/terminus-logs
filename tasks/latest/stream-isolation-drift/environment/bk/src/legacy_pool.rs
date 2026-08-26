/// Reference pool used by unit fixtures only.
pub fn legacy_draw(pool: &mut Vec<f64>, draws: &[f64]) {
    for value in draws {
        pool.push(*value);
    }
}

pub fn legacy_norm(pool: &[f64]) -> f64 {
    pool.iter().map(|v| v * v).sum::<f64>().sqrt()
}
