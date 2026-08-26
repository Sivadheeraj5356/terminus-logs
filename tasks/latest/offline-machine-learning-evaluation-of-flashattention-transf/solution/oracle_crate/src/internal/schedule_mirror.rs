//! Combinatorial Blueprint: plan materializes a disk schedule.mir witness; seal folds CRC32 of
//! those bytes so in-memory visit_checksum alone cannot seal correctly.
//! Axiomatic Blindspot: SCH1 + little-endian visit triples in visit order ⇒ CRC axiom; agents
//! must not invent alternate orderings.
//! Silent Failure: skipping mir write or hashing CRC(visit_checksum) instead of file bytes.

use super::app_root;
use anyhow::{Context, Result};
use std::fs;
use std::path::Path;

pub fn mir_path() -> String {
    app_root::join_str("data/schedule.mir")
}

/// IEEE CRC-32 (poly 0xEDB88320), same family used by ZIP/PNG.
pub fn crc32_ieee(data: &[u8]) -> u32 {
    let mut crc = 0xffff_ffff_u32;
    for &b in data {
        crc ^= u32::from(b);
        for _ in 0..8 {
            if crc & 1 != 0 {
                crc = (crc >> 1) ^ 0xEDB8_8320;
            } else {
                crc >>= 1;
            }
        }
    }
    !crc
}

pub fn write_schedule_mir(visits: &[(u32, u32, u32)]) -> Result<()> {
    let path = mir_path();
    if let Some(parent) = Path::new(&path).parent() {
        fs::create_dir_all(parent)?;
    }
    let mut bytes = Vec::with_capacity(8 + visits.len() * 12);
    bytes.extend_from_slice(b"SCH1");
    bytes.extend_from_slice(&(visits.len() as u32).to_le_bytes());
    for &(h, qi, kj) in visits {
        bytes.extend_from_slice(&h.to_le_bytes());
        bytes.extend_from_slice(&qi.to_le_bytes());
        bytes.extend_from_slice(&kj.to_le_bytes());
    }
    fs::write(&path, &bytes).with_context(|| format!("write {path}"))?;
    Ok(())
}

pub fn clear_schedule_mir() {
    let _ = fs::remove_file(mir_path());
}

/// CRC32 of on-disk mir bytes; **0** when the file is missing/unreadable.
pub fn schedule_crc_from_disk() -> u32 {
    match fs::read(mir_path()) {
        Ok(b) => crc32_ieee(&b),
        Err(_) => 0,
    }
}
