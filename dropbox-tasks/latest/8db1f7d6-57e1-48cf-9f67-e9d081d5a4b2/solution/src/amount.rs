use crate::types::MAX_U64;

pub fn positive_qty(s: &str) -> Option<u64> {
    if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    if s.len() > 1 && s.starts_with('0') {
        return None;
    }
    let v = s.parse::<u64>().ok()?;
    if (1..=MAX_U64).contains(&v) {
        Some(v)
    } else {
        None
    }
}

pub fn control_qty_ok(s: &str) -> bool {
    matches!(s, "0" | "+0" | "-0")
}
