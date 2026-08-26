//! Offline annex header scanner (diagnostics only).

pub fn scan_hdr(bytes: &[u8]) -> usize {
    let mut n = 0usize;
    for w in bytes.windows(2) {
        if w[0] == b'L' && w[1].is_ascii_digit() {
            n = n.wrapping_add(1);
        }
    }
    n
}
