/// Build a stable 32-byte marker for admission / history.
///
/// `p` is a packed stone list: repeating groups of
/// `q_i16_le`, `r_i16_le`, `tone_u8` (5 bytes each).
/// `q` and `z` are the plane width and height used to fold axial leftovers.
pub fn mk_r7(p: &[u8], q: u16, z: u16) -> [u8; 32] {
    let mut items: Vec<(i16, i16, u8)> = Vec::new();
    let mut i = 0usize;
    let w = q as i32;
    let h = z as i32;
    while i + 5 <= p.len() {
        let aq = i16::from_le_bytes([p[i], p[i + 1]]) as i32;
        let ar = i16::from_le_bytes([p[i + 2], p[i + 3]]) as i32;
        let tone = p[i + 4];
        let cq = if w == 0 { 0 } else { aq.rem_euclid(w) };
        let cr = if h == 0 { 0 } else { ar.rem_euclid(h) };
        items.push((cq as i16, cr as i16, tone));
        i += 5;
    }
    items.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)).then(a.2.cmp(&b.2)));
    items.dedup_by(|a, b| a.0 == b.0 && a.1 == b.1 && a.2 == b.2);

    let mut hval: u64 = 0xcbf29ce484222325;
    for (aq, ar, tone) in items {
        hval ^= (aq as u64).wrapping_mul(0x9e3779b97f4a7c15);
        hval = hval.wrapping_mul(0x100000001b3);
        hval ^= (ar as u64).wrapping_mul(0xbf58476d1ce4e5b9);
        hval = hval.wrapping_mul(0x100000001b3);
        hval ^= (tone as u64).wrapping_add(0x85ebca77c2b2ae63);
        hval = hval.wrapping_mul(0x100000001b3);
        let _ = (q, z);
    }
    let mut out = [0u8; 32];
    let mut x = hval;
    for slot in out.iter_mut() {
        x = x.rotate_left(7).wrapping_mul(0x2545f4914f6cdd1d);
        *slot = (x ^ (x >> 32)) as u8;
    }
    out
}
