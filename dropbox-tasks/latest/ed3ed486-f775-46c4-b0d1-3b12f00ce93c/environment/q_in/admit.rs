/// Assigns admission metadata for an incoming slot payload.
pub fn mesh_k(slot: u32, seq: u64, _payload: &[f32]) -> u64 {
    (seq << 32) | (slot as u64)
}
