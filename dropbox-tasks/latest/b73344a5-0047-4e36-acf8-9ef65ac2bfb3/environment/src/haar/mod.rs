//! Haar discrete wavelet transform helpers.

pub fn max_levels_for_length(n: usize) -> u32 {
    if n < 2 {
        return 0;
    }
    let mut v = n;
    let mut levels = 0u32;
    while v >= 2 {
        levels += 1;
        v /= 2;
    }
    levels
}

pub fn clamp_levels(requested: u32, max_levels: u32, n: usize) -> u32 {
    let lmax = max_levels_for_length(n);
    requested.min(max_levels).min(lmax)
}

pub fn forward_haar_level(samples: &[f64]) -> (Vec<f64>, Vec<f64>, usize) {
    let pre_pad = samples.len();
    let mut work = samples.to_vec();
    if work.len() % 2 == 1 {
        work.push(0.0);
    }
    let pairs = work.len() / 2;
    let mut approx = Vec::with_capacity(pairs);
    let mut detail = Vec::with_capacity(pairs);
    for i in 0..pairs {
        let x0 = work[2 * i];
        let x1 = work[2 * i + 1];
        approx.push((x0 + x1) / 2.0);
        detail.push((x0 - x1) / 2.0);
    }
    (approx, detail, pre_pad)
}

pub fn inverse_haar_level(approx: &[f64], detail: &[f64], pre_pad: usize) -> Vec<f64> {
    assert_eq!(approx.len(), detail.len());
    let mut out = Vec::with_capacity(approx.len() * 2);
    for i in 0..approx.len() {
        let a = approx[i];
        let d = detail[i];
        out.push((a - d) / 2.0);
        out.push((a + d) / 2.0);
    }
    if out.len() > pre_pad {
        out.truncate(pre_pad);
    }
    out
}

pub fn forward_pyramid(samples: &[f64], levels: u32) -> (Vec<f64>, Vec<Vec<f64>>, Vec<usize>) {
    let mut approx = samples.to_vec();
    let mut details = Vec::new();
    let mut pads = Vec::new();
    for _ in 0..levels {
        let (a, d, pre) = forward_haar_level(&approx);
        pads.push(pre);
        details.push(d);
        approx = a;
    }
    (approx, details, pads)
}

pub fn inverse_pyramid(approx: &[f64], details: &[Vec<f64>], pads: &[usize]) -> Vec<f64> {
    let mut a = approx.to_vec();
    for lvl in (0..details.len()).rev() {
        a = inverse_haar_level(&a, &details[lvl], pads[lvl]);
    }
    a
}
