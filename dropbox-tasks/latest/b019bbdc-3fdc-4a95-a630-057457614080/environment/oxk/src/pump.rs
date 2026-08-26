/// Compute span draw and admit flag.
pub fn draw_v(cool: f64, channels: i32, per_ch: f64, cap: f64) -> (f64, bool) {
    let ch = f64::from(channels);
    let incremental = ch * per_ch;
    let residual = if cool.is_finite() { cool.max(0.0) } else { 0.0 };
    let used = residual + incremental;
    let lim = cap + 1e-9;
    let ok = incremental <= lim;
    (used, ok)
}
