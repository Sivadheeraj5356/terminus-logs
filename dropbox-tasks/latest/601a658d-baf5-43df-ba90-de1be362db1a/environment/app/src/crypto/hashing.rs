use super::sha256;

const ITERATIONS: u32 = 4096;

pub fn hash_password(password: &str, salt: &str) -> String {
    let mut current = format!("{}{}", salt, password).into_bytes();
    for _ in 0..ITERATIONS {
        current = sha256::digest(&current).to_vec();
    }
    sha256::hex(&current)
}

pub fn verify_password(password: &str, salt: &str, expected_hash: &str) -> bool {
    let candidate = hash_password(password, salt);
    constant_time_eq(candidate.as_bytes(), expected_hash.as_bytes())
}

pub fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut diff = 0u8;
    for i in 0..a.len() {
        diff |= a[i] ^ b[i];
    }
    diff == 0
}
