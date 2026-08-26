//! Spinal seal trailer: tip XOR profile.spine_salt, validated by the next plan.
use super::app_root;
use anyhow::{bail, Result};
use std::fs;
use std::path::Path;

pub fn trailer_path() -> String {
    app_root::join_str("var/spine_trailer.hex")
}

pub fn mark(tip: u64, spine_salt: u64) -> u64 {
    tip ^ spine_salt
}

pub fn encode_hex(mark: u64) -> String {
    format!("{mark:016x}")
}

pub fn decode_hex(s: &str) -> Result<u64> {
    let t = s.trim();
    if t.len() != 16 || !t.chars().all(|c| c.is_ascii_hexdigit()) {
        bail!("bad spine trailer hex");
    }
    Ok(u64::from_str_radix(t, 16)?)
}

pub fn persist(mark: u64) -> Result<()> {
    let path = trailer_path();
    if let Some(parent) = Path::new(&path).parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, encode_hex(mark))?;
    Ok(())
}

pub fn clear() {
    let _ = fs::remove_file(trailer_path());
}

pub fn load_optional() -> Result<Option<u64>> {
    let path = trailer_path();
    if !Path::new(&path).exists() {
        return Ok(None);
    }
    let raw = fs::read_to_string(&path)?;
    Ok(Some(decode_hex(&raw)?))
}

/// When a trailer exists, it must equal tip XOR spine_salt before plan mutates the ledger.
pub fn require_valid(tip: u64, spine_salt: u64) -> Result<()> {
    if let Some(got) = load_optional()? {
        let want = mark(tip, spine_salt);
        if got != want {
            bail!("stale spine trailer");
        }
    }
    Ok(())
}
