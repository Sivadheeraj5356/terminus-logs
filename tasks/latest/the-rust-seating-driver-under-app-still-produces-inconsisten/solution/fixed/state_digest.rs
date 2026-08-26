use crate::ledger::SeatLedger;
use sha2::{Digest, Sha256};

pub fn state_digest(ledger: &SeatLedger) -> String {
    let mut hasher = Sha256::new();
    let mut keys: Vec<_> = ledger.snapshot().keys().cloned().collect();
    keys.sort();
    for ram_id in keys {
        let rec = ledger.ram_record(&ram_id).expect("snapshot key");
        hasher.update(ram_id.as_bytes());
        hasher.update(rec.checksum.to_le_bytes());
        hasher.update(rec.tonnage_kg.to_le_bytes());
        hasher.update(rec.cycle_epoch.to_le_bytes());
    }
    hasher.update(ledger.cycle_epoch().to_le_bytes());
    hasher.update(ledger.journal_revision().to_le_bytes());
    format!("{:x}", hasher.finalize())
}
