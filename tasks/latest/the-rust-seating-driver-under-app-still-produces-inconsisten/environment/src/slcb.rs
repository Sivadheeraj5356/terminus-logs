use std::fs;
use std::path::Path;

use crate::path_norm::normalize_slice_path;

const MAGIC: &[u8; 4] = b"SLCB";

pub fn payload_checksum(payload: &[u8]) -> u32 {
    payload.iter().fold(0u32, |acc, b| acc.wrapping_add(*b as u32))
}

pub fn read_slcb_block(path: &Path) -> Result<(String, u32), String> {
    let bytes = fs::read(path).map_err(|e| e.to_string())?;
    if bytes.len() < 12 {
        return Err("slice descriptor too short".into());
    }
    if &bytes[0..4] != MAGIC {
        return Err("bad slice magic".into());
    }
    let len = u32::from_le_bytes(bytes[4..8].try_into().unwrap()) as usize;
    if bytes.len() < 8 + len + 4 {
        return Err("slice descriptor truncated".into());
    }
    let payload = &bytes[8..8 + len];
    let stored = u32::from_le_bytes(bytes[8 + len..8 + len + 4].try_into().unwrap());
    let expected = payload_checksum(payload);
    if stored != expected {
        return Err(format!(
            "checksum mismatch for {}: stored={stored} expected={expected}",
            path.display()
        ));
    }
    let slice_path = String::from_utf8(payload.to_vec()).map_err(|e| e.to_string())?;
    Ok((normalize_slice_path(&slice_path), expected))
}

pub fn slice_path(data_root: &str, block_id: &str) -> String {
    format!("{data_root}/slices/{block_id}.bin")
}
