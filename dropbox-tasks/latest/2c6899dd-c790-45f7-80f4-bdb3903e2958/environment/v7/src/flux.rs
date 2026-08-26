/// Build a stable 32-byte marker for admission / history.
///
/// `p` is a packed stone list: repeating groups of
/// `q_i16_le`, `r_i16_le`, `tone_u8` (5 bytes each).
/// `q` and `z` are the plane width and height used to fold axial leftovers.
pub fn mk_r7(p: &[u8], q: u16, z: u16) -> [u8; 32] {
    let mut out = [0u8; 32];
    let mut h: u64 = 0xcbf29ce484222325;
    let mut i = 0usize;
    while i + 5 <= p.len() {
        let aq = i16::from_le_bytes([p[i], p[i + 1]]);
        let ar = i16::from_le_bytes([p[i + 2], p[i + 3]]);
        let tone = p[i + 4];
        let mixed = (aq as i32)
            .wrapping_mul(z as i32)
            .wrapping_add(ar as i32)
            .wrapping_add((q as i32).wrapping_shl(3));
        h ^= (mixed as u64).wrapping_mul(0x9e3779b97f4a7c15);
        h ^= (tone as u64).wrapping_add(0x100000001b3);
        h = h.wrapping_mul(0x100000001b3);
        i += 5;
    }
    for (k, slot) in out.iter_mut().enumerate() {
        *slot = ((h >> ((k % 8) * 8)) as u8).wrapping_add((k as u8).wrapping_mul(17));
        h = h.rotate_left(3).wrapping_mul(0xbf58476d1ce4e5b9);
    }
    out
}
