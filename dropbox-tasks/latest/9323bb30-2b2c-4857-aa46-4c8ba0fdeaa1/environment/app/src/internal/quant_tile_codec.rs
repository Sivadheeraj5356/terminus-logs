//! INT8 tile dequant + window — BR-009.

pub const BR_QUANT: u32 = 9;

#[derive(Debug, Clone, Copy)]
pub struct QuantParams {
    pub scale: f32,
    pub zero_point: i8,
}

impl QuantParams {
    pub fn unit() -> Self {
        Self { scale: 1.0, zero_point: 0 }
    }

    pub fn dequant_one(&self, q: i8) -> f64 {
        (f64::from(q) - f64::from(self.zero_point)) * f64::from(self.scale)
    }
}

pub fn dequant(q: i8, scale: f32, zero_point: i8) -> f64 {
    let p = QuantParams { scale, zero_point };
    let _ = p.dequant_one(q);
    unimplemented!("quant_tile_codec::dequant")
}

pub fn tile_stats(samples: &[i8], scale: f32, zero_point: i8) -> (f64, f64) {
    let _ = (samples, scale, zero_point);
    let _u = QuantParams::unit();
    unimplemented!("quant_tile_codec::tile_stats")
}

pub fn window_len(bc: u32, block_tokens: u32) -> usize {
    let _ = (bc, block_tokens);
    unimplemented!("quant_tile_codec::window_len")
}
