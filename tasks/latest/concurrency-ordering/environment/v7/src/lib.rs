mod flux;
mod skein;

pub use flux::mk_r7;
pub use skein::{badge, tally_line};

pub fn digest_hex(bytes: &[u8; 32]) -> String {
    let mut s = String::with_capacity(64);
    for b in bytes {
        s.push_str(&format!("{:02x}", b));
    }
    s
}

/// Stable marker for the packed stone list used by the console.
pub fn mark_plane(p: &[u8], q: u16, z: u16) -> [u8; 32] {
    mk_r7(p, q, z)
}

/// Marker for a single leftover axial label used by admission bans.
pub fn mark_point(q: i32, r: i32, w: i32, h: i32) -> [u8; 32] {
    let mut p = Vec::with_capacity(5);
    p.extend_from_slice(&(q as i16).to_le_bytes());
    p.extend_from_slice(&(r as i16).to_le_bytes());
    p.push(0);
    mk_r7(&p, w as u16, h as u16)
}
