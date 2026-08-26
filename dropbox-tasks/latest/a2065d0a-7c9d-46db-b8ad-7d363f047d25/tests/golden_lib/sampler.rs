pub fn conditional(n_dk: u64, n_kw: u64, n_k: u64, alpha: f64, beta: f64, v: usize) -> f64 {
    (n_dk as f64 + alpha) * (n_kw as f64 + beta) / (n_k as f64 + v as f64 * beta)
}

pub fn choose(masses: &[f64], draw: f64) -> usize {
    let mut cumulative = 0.0f64;
    for (topic, &mass) in masses.iter().enumerate() {
        cumulative += mass;
        if cumulative > draw {
            return topic;
        }
    }
    masses.len() - 1
}
