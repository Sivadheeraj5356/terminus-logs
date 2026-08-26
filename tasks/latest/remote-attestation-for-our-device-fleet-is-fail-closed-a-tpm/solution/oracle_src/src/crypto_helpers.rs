//! SHA-256 and P-256 helpers for candidates.
//! Does not implement quote authentication or acceptance decisions.

use p256::ecdsa::{Signature, VerifyingKey};
use p256::elliptic_curve::generic_array::GenericArray;
use sha2::{Digest, Sha256};

use crate::hexutil;

pub fn sha256(data: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(data);
    let out = h.finalize();
    let mut arr = [0u8; 32];
    arr.copy_from_slice(&out);
    arr
}

pub fn parse_sec1_verifying_key(sec1: &[u8]) -> Result<VerifyingKey, String> {
    if sec1.len() != 65 || sec1[0] != 0x04 {
        return Err("invalid SEC1 point encoding".into());
    }
    VerifyingKey::from_sec1_bytes(sec1).map_err(|e| format!("invalid P-256 public key: {e}"))
}

pub fn fingerprint_public_key_sec1(sec1: &[u8]) -> String {
    hexutil::encode_lower_hex(&sha256(sec1))
}

/// Construct an ECDSA signature from raw 32-byte r and s (no low-S forcing).
pub fn signature_from_raw_rs(r: &[u8], s: &[u8]) -> Result<Signature, String> {
    if r.len() != 32 || s.len() != 32 {
        return Err("r and s must be 32 bytes".into());
    }
    if r.iter().all(|&b| b == 0) || s.iter().all(|&b| b == 0) {
        return Err("r or s is zero".into());
    }
    let mut raw = [0u8; 64];
    raw[..32].copy_from_slice(r);
    raw[32..].copy_from_slice(s);
    Signature::from_bytes(GenericArray::from_slice(&raw))
        .map_err(|e| format!("invalid ECDSA scalar range: {e}"))
}
