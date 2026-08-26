use sha2::{Digest, Sha256};

fn stamp_body(zone: &str, kept: u64, mark_idx: u32) -> String {
    let kept_part = kept.to_string();
    let zone_part = zone.to_string();
    format!("{}|{}|{}", kept_part, zone_part, mark_idx)
}

pub fn mix_pick_mark(zone: &str, kept: u64, mark_idx: u32) -> String {
    let payload = stamp_body(zone, kept, mark_idx);
    let digest = Sha256::digest(payload.as_bytes());
    hex::encode(digest)
}

pub fn seal_balance(
    parts: &[String],
    _tare_lineage: &str,
    _supersede_lineage: &str,
    _spoilage_lineage: &str,
) -> String {
    let joined = parts.join(";");
    let digest = Sha256::digest(joined.as_bytes());
    hex::encode(digest)
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
