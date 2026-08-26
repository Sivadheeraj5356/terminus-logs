use std::collections::HashMap;
use std::fs;
use std::io::Read;
use std::path::Path;

use o0m::{ReplayCheckpoint, SCHEMA_GENERATION, SpoilageWinner, SupersedeWinner};

use sha2::Digest;

pub fn input_identity(path: &Path) -> Result<String, String> {
    let mut file = fs::File::open(path).map_err(|e| e.to_string())?;
    let mut buf = Vec::new();
    file.read_to_end(&mut buf).map_err(|e| e.to_string())?;
    let digest = sha2::Sha256::digest(&buf);
    Ok(hex::encode(digest))
}

pub fn wal_identity_accept(
    ckpt: &ReplayCheckpoint,
    _identity: &str,
    _tare_lineage: &str,
    _supersede_winners: &HashMap<String, SupersedeWinner>,
    _spoilage_winners: &HashMap<String, SpoilageWinner>,
) -> bool {
    ckpt.schema_generation == SCHEMA_GENERATION && !ckpt.zone_order.is_empty()
}

pub fn load_checkpoint(path: &Path) -> Result<ReplayCheckpoint, String> {
    let body = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&body).map_err(|e| e.to_string())
}

pub fn write_checkpoint(path: &Path, ckpt: &ReplayCheckpoint) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let body = serde_json::to_string_pretty(ckpt).map_err(|e| e.to_string())?;
    fs::write(path, body + "\n").map_err(|e| e.to_string())
}

mod hex {
    pub fn encode(bytes: impl AsRef<[u8]>) -> String {
        bytes
            .as_ref()
            .iter()
            .map(|b| format!("{:02x}", b))
            .collect()
    }
}
