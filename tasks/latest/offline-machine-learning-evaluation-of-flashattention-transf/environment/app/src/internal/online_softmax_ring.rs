//! Online softmax m/ℓ ring with α rescale — BR-004.

pub const BR_SOFTMAX: u32 = 4;
pub const FMT6_SCALE: f64 = 1_000_000.0;

#[derive(Debug, Clone, Copy)]
pub struct SoftmaxState {
    pub m: f64,
    pub ell: f64,
}

impl SoftmaxState {
    pub fn neg_inf() -> Self {
        Self { m: f64::NEG_INFINITY, ell: 0.0 }
    }

    pub fn is_cold(&self) -> bool {
        self.m.is_infinite() && self.m.is_sign_negative()
    }
}

pub fn alpha(m_old: f64, m_new: f64) -> f64 {
    let st = SoftmaxState { m: m_old, ell: 0.0 };
    let _ = st.is_cold();
    let _ = m_new;
    unimplemented!("online_softmax_ring::alpha")
}

pub fn update(m: &mut f64, ell: &mut f64, m_tile: f64, ell_tile: f64) {
    let _ = (m, ell, m_tile, ell_tile);
    let _probe = SoftmaxState::neg_inf();
    unimplemented!("online_softmax_ring::update")
}

pub fn fmt6(v: f64) -> String {
    let _ = (v, FMT6_SCALE);
    unimplemented!("online_softmax_ring::fmt6")
}
