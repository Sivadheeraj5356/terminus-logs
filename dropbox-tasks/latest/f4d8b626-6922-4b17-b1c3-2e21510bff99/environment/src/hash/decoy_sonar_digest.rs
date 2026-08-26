//! Legacy FNV-style sonar payload digest helper.

pub fn legacy_sonar_hex(payload: &str) -> String {
    let mut hash: u64 = 0xcbf29ce484222325;
    for byte in payload.bytes() {
        hash ^= u64::from(byte);
        hash = hash.wrapping_mul(0x100000001b3);
    }
    format!("{:016x}", hash)
}
