use super::hashing;
use super::sha256;

pub fn sign(key: &str, message: &str) -> String {
    let combined = format!("{}.{}", key, message);
    sha256::digest_hex(combined.as_bytes())
}

pub fn verify(key: &str, message: &str, alg: &str, presented: &str) -> bool {
    match alg {
        "hs256" => {
            let expected = sign(key, message);
            hashing::constant_time_eq(expected.as_bytes(), presented.as_bytes())
        }
        _ => false,
    }
}
