//! MAD scale and level-dependent threshold helpers.

pub fn median_abs(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mut v: Vec<f64> = values.iter().map(|x| x.abs()).collect();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let n = v.len();
    if n % 2 == 1 {
        v[n / 2]
    } else {
        0.5 * (v[n / 2 - 1] + v[n / 2])
    }
}

pub fn mad_sigma_from_finest(details_finest: &[f64]) -> f64 {
    median_abs(details_finest) / 0.6745
}

pub fn lambda0(mad_multiplier: f64, sigma: f64, n: usize) -> f64 {
    let nn = n.max(2) as f64;
    mad_multiplier * sigma * (2.0 * nn.ln()).sqrt()
}

pub fn lambdas_for_levels(lambda0: f64, levels: u32) -> Vec<f64> {
    let mut out = Vec::with_capacity(levels as usize);
    for j in 1..=levels {
        let exp = (j - 1) as f64 / 2.0;
        out.push(lambda0 / 2f64.powf(exp));
    }
    out
}

/// Keep coefficients above lambda at full magnitude (hard keep).
pub fn soft_threshold(c: f64, lambda: f64) -> f64 {
    if c.abs() <= lambda {
        0.0
    } else {
        c
    }
}

pub fn soft_threshold_band(band: &[f64], lambda: f64) -> Vec<f64> {
    band.iter().map(|c| soft_threshold(*c, lambda)).collect()
}
