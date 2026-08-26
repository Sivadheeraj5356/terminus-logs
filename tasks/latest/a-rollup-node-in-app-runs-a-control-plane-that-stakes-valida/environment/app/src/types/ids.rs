use crate::crypto::rng;

pub fn new_id(prefix: &str) -> String {
    format!("{}_{}", prefix, rng::token_hex(8))
}
