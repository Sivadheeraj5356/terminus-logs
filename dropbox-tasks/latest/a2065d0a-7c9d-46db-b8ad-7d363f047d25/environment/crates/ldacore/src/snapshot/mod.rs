use sha2::{Digest, Sha256};

pub const COUNTS_SEPARATOR: &[u8] = b"\n--counts--\n";

pub fn checksum(corpus: &[u8], counts: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(corpus);
    h.update(COUNTS_SEPARATOR);
    h.update(counts);
    format!("{:x}", h.finalize())
}
