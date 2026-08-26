//! Decoy spectral denoiser — not on the authoritative Haar pipeline path.
//! Agents may edit this module, but reconstruct-export does not call it.

pub fn fft_style_soft_gate(samples: &[f64], cutoff: f64) -> Vec<f64> {
    samples
        .iter()
        .map(|x| if x.abs() < cutoff { 0.0 } else { *x })
        .collect()
}

pub fn moving_average_denoise(samples: &[f64], window: usize) -> Vec<f64> {
    if window == 0 || samples.is_empty() {
        return samples.to_vec();
    }
    let mut out = Vec::with_capacity(samples.len());
    for i in 0..samples.len() {
        let start = i.saturating_sub(window / 2);
        let end = (i + window / 2 + 1).min(samples.len());
        let slice = &samples[start..end];
        let mean = slice.iter().sum::<f64>() / slice.len() as f64;
        out.push(mean);
    }
    out
}
