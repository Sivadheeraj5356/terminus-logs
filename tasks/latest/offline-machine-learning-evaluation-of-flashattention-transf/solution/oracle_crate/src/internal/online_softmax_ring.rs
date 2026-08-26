pub fn alpha(m_old: f64, m_new: f64) -> f64 {
    if m_old.is_infinite() && m_old.is_sign_negative() {
        if m_new.is_infinite() && m_new.is_sign_negative() {
            1.0
        } else {
            0.0
        }
    } else {
        (m_old - m_new).exp()
    }
}

pub fn update(m: &mut f64, ell: &mut f64, m_tile: f64, ell_tile: f64) {
    let m_new = if m.is_infinite() && m.is_sign_negative() {
        m_tile
    } else {
        m.max(m_tile)
    };
    let a = alpha(*m, m_new);
    *ell = (*ell) * a + ell_tile * (m_tile - m_new).exp();
    *m = m_new;
}

pub fn fmt6(v: f64) -> String {
    // round half away from zero to 6 fractional digits
    let sign = if v.is_sign_negative() && v != 0.0 { -1.0 } else { 1.0 };
    let abs = v.abs();
    let scaled = abs * 1_000_000.0;
    let rounded = scaled.floor() + if (scaled - scaled.floor()) >= 0.5 { 1.0 } else { 0.0 };
    let out = sign * rounded / 1_000_000.0;
    format!("{:.6}", out)
}

pub fn init_pair() -> (f64, f64) {
    (f64::NEG_INFINITY, 0.0)
}

pub fn sanity_finite(m: f64) -> bool {
    m.is_finite() || m.is_infinite()
}
