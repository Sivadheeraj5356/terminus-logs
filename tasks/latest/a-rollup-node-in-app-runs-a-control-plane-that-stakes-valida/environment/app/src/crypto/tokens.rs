use super::sha256;

pub fn mint_secret() -> String {
    super::rng::token_hex(24)
}

pub fn fingerprint(secret: &str) -> String {
    sha256::digest_hex(secret.as_bytes())
}
