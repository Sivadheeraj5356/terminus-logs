use prlg_k4::ReclaimRow;
use sha2::{Digest, Sha256};

pub fn journal_digest(rows: &[ReclaimRow]) -> String {
    let mut sorted = rows.to_vec();
    sorted.sort_by_key(|r| (r.round_index, r.socket_id));
    let mut hasher = Sha256::new();
    for row in sorted {
        hasher.update(row.socket_id.to_le_bytes());
        hasher.update([0x1f]);
        hasher.update(row.shard.to_le_bytes());
        hasher.update([0x1f]);
        hasher.update(row.event.as_bytes());
    }
    hex::encode(hasher.finalize())
}
