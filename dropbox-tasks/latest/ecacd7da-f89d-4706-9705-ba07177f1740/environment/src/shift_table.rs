use crate::ledger::SeatLedger;
use serde_json::{json, Value};
use std::collections::BTreeMap;

pub fn materialize_shift_table(index: &SeatLedger) -> Value {
    let mut rams = BTreeMap::new();
    for (key, rec) in index.snapshot() {
        rams.insert(
            key,
            json!({
                "checksum": rec.checksum,
                "tonnage_kg": rec.tonnage_kg,
                "cycle_epoch": rec.cycle_epoch
            }),
        );
    }
    json!({
        "cycle_epoch": index.cycle_epoch(),
        "journal_revision": index.journal_revision(),
        "rams": rams,
        "ram_count": rams.len(),
    })
}
