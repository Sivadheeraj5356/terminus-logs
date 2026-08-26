pub fn dequant(q: i8, scale: f32, zero_point: i8) -> f64 {
    (f64::from(q) - f64::from(zero_point)) * f64::from(scale)
}

pub fn tile_stats(samples: &[i8], scale: f32, zero_point: i8) -> (f64, f64) {
    if samples.is_empty() {
        return (f64::NEG_INFINITY, 0.0);
    }
    let xs: Vec<f64> = samples
        .iter()
        .map(|q| dequant(*q, scale, zero_point))
        .collect();
    let mut m_tile = f64::NEG_INFINITY;
    for x in &xs {
        if *x > m_tile {
            m_tile = *x;
        }
    }
    let mut ell_tile = 0.0;
    for x in &xs {
        ell_tile += (x - m_tile).exp();
    }
    (m_tile, ell_tile)
}

pub fn window_len(bc: u32, block_tokens: u32) -> usize {
    bc.min(block_tokens) as usize
}
