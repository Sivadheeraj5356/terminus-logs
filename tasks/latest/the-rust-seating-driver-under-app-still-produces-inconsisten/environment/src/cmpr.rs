use std::fs;
use std::path::Path;

const MAGIC: &[u8; 4] = b"CMPR";

pub fn payload_checksum(payload: &[u8]) -> u32 {
    payload.iter().fold(0u32, |acc, b| acc.wrapping_add(*b as u32))
}

pub struct CmprPayload {
    pub ram_id: String,
    pub tonnage_kg: u32,
}

pub fn parse_payload(text: &str) -> Result<CmprPayload, String> {
    let (ram_id, tonnage_raw) = text
        .split_once('|')
        .ok_or_else(|| "cmpr payload missing tonnage separator".to_string())?;
    let tonnage_kg = tonnage_raw
        .parse::<u32>()
        .map_err(|e| format!("invalid tonnage: {e}"))?;
    Ok(CmprPayload {
        ram_id: ram_id.to_string(),
        tonnage_kg,
    })
}

pub fn read_cmpr_block(path: &Path) -> Result<(CmprPayload, u32), String> {
    let bytes = fs::read(path).map_err(|e| e.to_string())?;
    if bytes.len() < 12 {
        return Err("cmpr block too short".into());
    }
    if &bytes[0..4] != MAGIC {
        return Err("bad cmpr magic".into());
    }
    let len = u32::from_le_bytes(bytes[4..8].try_into().unwrap()) as usize;
    if bytes.len() < 8 + len + 4 {
        return Err("cmpr block truncated".into());
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
    let text = String::from_utf8(payload.to_vec()).map_err(|e| e.to_string())?;
    let parsed = parse_payload(&text)?;
    Ok((parsed, expected))
}

pub fn ram_block_path(data_root: &str, ram_block_id: &str) -> String {
    format!("{data_root}/{ram_block_id}.bin")
}
