//! Strict lowercase hex decode/encode helpers.

pub fn decode_lower_hex(s: &str) -> Result<Vec<u8>, String> {
    if s.len() % 2 != 0 {
        return Err("odd-length hex".into());
    }
    if s.chars().any(|c| c.is_ascii_uppercase() || c.is_whitespace() || c == 'x') {
        // Reject uppercase, whitespace, and 0x-style prefixes (contains 'x').
        if s.starts_with("0x") || s.starts_with("0X") {
            return Err("hex must not include 0x prefix".into());
        }
        if s.chars().any(|c| c.is_ascii_uppercase()) {
            return Err("hex must be lowercase".into());
        }
        if s.chars().any(|c| c.is_whitespace()) {
            return Err("hex must not contain whitespace".into());
        }
    }
    hex::decode(s).map_err(|e| format!("invalid hex: {e}"))
}

pub fn encode_lower_hex(bytes: &[u8]) -> String {
    hex::encode(bytes)
}

pub fn require_exact_lower_hex(s: &str, nbytes: usize) -> Result<Vec<u8>, String> {
    if s.len() != nbytes * 2 {
        return Err(format!("expected {} hex chars, got {}", nbytes * 2, s.len()));
    }
    decode_lower_hex(s)
}
