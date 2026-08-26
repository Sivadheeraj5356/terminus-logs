//! IPv4 dotted-quad parsing. Frozen evidence.

/// Parse a dotted-quad into a big-endian u32. Rejects leading zeros and
/// out-of-range octets.
pub fn parse_ip(s: &str) -> Option<u32> {
    let mut parts = s.split('.');
    let mut v: u32 = 0;
    let mut count = 0;
    for p in parts.by_ref() {
        count += 1;
        if count > 4 {
            return None;
        }
        if p.is_empty() || !p.bytes().all(|b| b.is_ascii_digit()) {
            return None;
        }
        if p.len() > 1 && p.as_bytes()[0] == b'0' {
            return None;
        }
        let n: u32 = p.parse().ok()?;
        if n > 255 {
            return None;
        }
        v = (v << 8) | n;
    }
    if count == 4 {
        Some(v)
    } else {
        None
    }
}
