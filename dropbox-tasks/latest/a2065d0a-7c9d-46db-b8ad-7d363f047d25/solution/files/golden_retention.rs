pub fn should_accumulate(sweep: usize, burn_in: usize) -> bool {
    sweep > burn_in
}

pub fn accumulate(theta_sum: &mut [Vec<f64>], n_dk: &[Vec<u64>], alpha: f64, k: usize) {
    for (d, row) in n_dk.iter().enumerate() {
        let mut total = 0u64;
        for &count in row {
            total += count;
        }
        let denom = total as f64 + k as f64 * alpha;
        for topic in 0..k {
            theta_sum[d][topic] += (row[topic] as f64 + alpha) / denom;
        }
    }
}

pub fn retained_count(sweeps: usize, burn_in: usize) -> usize {
    sweeps - burn_in
}
