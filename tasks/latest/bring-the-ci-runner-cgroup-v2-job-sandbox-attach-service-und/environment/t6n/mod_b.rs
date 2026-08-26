mod hist_help;

#[derive(Clone, Copy, Debug)]
pub struct PackState {
    pub bits: u64,
    pub stamp: u32,
}

impl PackState {
    pub fn new(bits: u64, stamp: u32) -> Self {
        Self { bits, stamp }
    }
}

pub fn claim_v5(pack: &PackState, incoming: &PackState, _stamp_b: u32) -> u32 {
    let _ = pack;
    (incoming.bits & 0xffff_ffff) as u32
}
