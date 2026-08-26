pub mod emit_r;

pub fn board_digest(cells: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf29ce484222325;
    for (i, b) in cells.iter().enumerate() {
        h ^= (*b as u64).wrapping_add(i as u64);
        h = h.wrapping_mul(0x100000001b3);
    }
    h
}
