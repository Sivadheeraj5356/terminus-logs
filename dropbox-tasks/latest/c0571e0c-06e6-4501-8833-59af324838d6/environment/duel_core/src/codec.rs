use crate::state::GameState;
use sha2::{Digest, Sha256};

pub fn serialize(state: &GameState) -> [u8; 6] {
    [
        state.p0.pos,
        state.p0.hp,
        state.p0.meter,
        state.p1.pos,
        state.p1.hp,
        state.p1.meter,
    ]
}

pub fn digest_hex(bytes: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(bytes);
    format!("{:x}", h.finalize())
}
