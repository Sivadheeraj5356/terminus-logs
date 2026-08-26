use std::fmt::Write as _;

pub fn valid_identifier(value: &str) -> bool {
    let mut chars = value.chars();
    match chars.next() {
        Some(c) if c.is_ascii_uppercase() => {}
        _ => return false,
    }
    if value.len() > 16 {
        return false;
    }
    chars.all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || c == '_')
}

pub fn parse_canonical_i32(value: &str) -> Option<i32> {
    if value == "0" {
        return Some(0);
    }
    let bytes = value.as_bytes();
    if bytes.is_empty() || value.starts_with('+') || value == "-0" {
        return None;
    }
    let digits = if bytes[0] == b'-' { &bytes[1..] } else { bytes };
    if digits.is_empty() || digits[0] == b'0' || !digits.iter().all(u8::is_ascii_digit) {
        return None;
    }
    value.parse::<i32>().ok()
}

pub fn fnv1a64(bytes: &[u8]) -> u64 {
    let mut hash = 14_695_981_039_346_656_037u64;
    for byte in bytes {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(1_099_511_628_211u64);
    }
    hash
}

pub fn hash_hex(bytes: &[u8]) -> String {
    format!("{:016x}", fnv1a64(bytes))
}

pub fn json_string(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 2);
    out.push('"');
    for c in value.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c < ' ' => {
                let _ = write!(&mut out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out.push('"');
    out
}
